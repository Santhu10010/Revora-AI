"""FastAPI backend for Revora AI."""
import os
import json
from pathlib import Path
import hashlib
import pandas as pd
from io import BytesIO
from typing import Optional
from datetime import datetime
import traceback

from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from backend.pipeline.analyze import analyze
from backend.schemas import AnalysisResults, SimulateRequest, SimulateResponse

app = FastAPI(title="Revora AI", version="0.1.0")

# CORS
CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGIN, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache for analyses (lite mode, no DB)
ANALYSES_CACHE = {}

# Mode
APP_MODE = os.getenv("APP_MODE", "lite")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "mode": APP_MODE,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/analyze")
async def analyze_upload(
    file: UploadFile = File(...),
    mode: Optional[str] = None
):
    """
    Upload a CSV/XLSX file and run analysis.
    Returns analysis_id, summary, top issues, safety alerts, warnings.
    """
    try:
        mode = mode or APP_MODE

        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        if not file.filename.lower().endswith(('.csv', '.xlsx')):
            raise HTTPException(status_code=400, detail="Only CSV and XLSX files supported")

        # Read file
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="File is empty")

        # Parse based on extension
        try:
            if file.filename.lower().endswith('.csv'):
                last_error = None
                for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
                    try:
                        df = pd.read_csv(BytesIO(content), encoding=encoding)
                        break
                    except (UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
                        last_error = exc
                else:
                    raise last_error or ValueError('Unable to decode CSV file')
            else:
                try:
                    df = pd.read_excel(BytesIO(content))
                except Exception as exc:
                    raise ValueError(f"Invalid XLSX file: {exc}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

        if df.empty or df.shape[1] == 0 or all(str(col).strip() == '' for col in df.columns):
            raise HTTPException(status_code=400, detail="File is empty or has no usable columns")

        # Check upload size limits
        max_rows = 2000 if mode == 'lite' else 1000
        if len(df) > max_rows:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max {max_rows} rows for {mode} mode."
            )

        # Run analysis
        try:
            results = analyze(df, mode=mode)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Generate analysis ID
        file_hash = hashlib.md5(content).hexdigest()[:12]
        analysis_id = f"analysis_{file_hash}_{int(datetime.utcnow().timestamp())}"

        # Cache results
        ANALYSES_CACHE[analysis_id] = {
            "id": analysis_id,
            "filename": file.filename,
            "created_at": datetime.utcnow().isoformat(),
            "mode": mode,
            "results": results
        }

        # Build response
        top_issues = sorted(
            [
                {
                    "aspect": i.aspect,
                    "polarity": i.polarity,
                    "mentions": i.mentions,
                    "pct_negative": (i.mentions / results.meta.total_reviews) if results.meta.total_reviews > 0 else 0,
                    "damage": i.damage,
                    "priority_rank": i.priority_rank,
                    "confidence_label": i.confidence_label
                }
                for i in results.insights
                if i.polarity == 'neg'
            ],
            key=lambda x: x["priority_rank"]
        )[:5]

        return {
            "analysis_id": analysis_id,
            "filename": file.filename,
            "mode": mode,
            "review_count": results.meta.total_reviews,
            "avg_rating": results.meta.avg_rating,
            "rating_source": results.reviews[0].rating_source if results.reviews else "pseudo",
            "pct_negative": results.meta.pct_negative,
            "languages": results.meta.languages_detected,
            "top_issues": top_issues,
            "safety_alerts": results.meta.safety_cases,
            "warnings": results.meta.warnings,
            "processing_ms": results.meta.processing_ms
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/analyses")
def list_analyses():
    """List recent saved analyses."""
    return {
        "analyses": [
            {
                "id": v["id"],
                "filename": v["filename"],
                "created_at": v["created_at"],
                "mode": v["mode"],
                "review_count": v["results"].meta.total_reviews,
                "avg_rating": v["results"].meta.avg_rating
            }
            for v in ANALYSES_CACHE.values()
        ]
    }


@app.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    """Retrieve saved analysis summary."""
    if analysis_id not in ANALYSES_CACHE:
        raise HTTPException(status_code=404, detail="Analysis not found")

    cache_entry = ANALYSES_CACHE[analysis_id]
    results = cache_entry["results"]

    return {
        "analysis_id": analysis_id,
        "filename": cache_entry["filename"],
        "mode": cache_entry["mode"],
        "created_at": cache_entry["created_at"],
        "review_count": results.meta.total_reviews,
        "avg_rating": results.meta.avg_rating,
        "rating_source": results.reviews[0].rating_source if results.reviews else "pseudo",
        "pct_negative": results.meta.pct_negative,
        "languages": results.meta.languages_detected,
        "warnings": results.meta.warnings,
        "safety_alerts": results.meta.safety_cases,
        "top_issues": [
            {
                "aspect": i.aspect,
                "polarity": i.polarity,
                "mentions": i.mentions,
                "pct_negative": i.pct_negative,
                "damage": i.damage,
                "priority_rank": i.priority_rank,
                "confidence_label": i.confidence_label
            }
            for i in results.insights
            if i.polarity == 'neg'
        ][:5]
    }


@app.post("/api/analyses/{analysis_id}/actions")
def generate_actions(analysis_id: str, aspect: str, polarity: str):
    """
    Generate ticket and reply draft for an issue.
    """
    if analysis_id not in ANALYSES_CACHE:
        raise HTTPException(status_code=404, detail="Analysis not found")

    results = ANALYSES_CACHE[analysis_id]["results"]

    # Find the insight
    insight = None
    for i in results.insights:
        if i.aspect == aspect and i.polarity == polarity:
            insight = i
            break

    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    # Get top 3 evidence reviews
    evidence_clauses = [
        c for c in results.clauses
        if c.aspect == aspect and c.polarity == polarity
    ][:3]

    evidence_reviews = []
    for clause in evidence_clauses:
        review = next((r for r in results.reviews if r.review_id == clause.review_id), None)
        if review:
            evidence_reviews.append({
                "text": clause.clause_text,
                "rating": review.rating or "N/A"
            })

    # Determine team and priority from routing
    routing = {
        'battery': ('Product/Engineering', 'P2'),
        'camera': ('Product/Engineering', 'P2'),
        'display': ('Product/Engineering', 'P2'),
        'performance': ('Product/Engineering', 'P1'),
        'build_quality': ('Product/Engineering', 'P2'),
        'delivery': ('Logistics', 'P2'),
        'packaging': ('Logistics', 'P3'),
        'price': ('Pricing/Marketing', 'P3'),
    }

    team, priority = routing.get(aspect, ('Product', 'P2'))

    # Render templates
    try:
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader('backend/templates'))

        ticket_template = env.get_template('ticket.jinja2')
        reply_template = env.get_template('reply.jinja2')

        ticket = ticket_template.render(
            aspect=aspect,
            polarity=polarity,
            team=team,
            priority=priority,
            mentions=insight.mentions,
            damage=insight.damage or 0,
            pct_negative=insight.pct_negative * 100,
            priority_rank=insight.priority_rank,
            evidence=evidence_reviews
        )

        reply = reply_template.render(
            aspect=aspect
        )
    except Exception as e:
        # Fallback to plain text if templates not available
        ticket = f"Issue: {aspect} ({polarity})\nTeam: {team}\nPriority: {priority}\nMentions: {insight.mentions}"
        reply = f"Thank you for your feedback on {aspect}. We are working to improve this."

    return {
        "aspect": aspect,
        "polarity": polarity,
        "ticket": ticket,
        "reply": reply
    }


import csv
from io import StringIO
from fastapi.responses import StreamingResponse

@app.get("/api/analyses/{analysis_id}/export")
def export_analysis(analysis_id: str, format: str = "markdown"):
    """
    Export analysis results as Markdown or CSV.
    """
    if analysis_id not in ANALYSES_CACHE:
        raise HTTPException(status_code=404, detail="Analysis not found")

    results = ANALYSES_CACHE[analysis_id]["results"]

    if format == "markdown":
        md = f"# Analysis Report\n\n"
        md += f"**Reviews:** {results.meta.total_reviews}\n"
        md += f"**Average Rating:** {results.meta.avg_rating:.2f}\n"
        md += f"**Negative:** {results.meta.pct_negative:.1%}\n\n"

        md += "## Top Issues\n\n"
        for insight in results.insights[:5]:
            if insight.polarity == 'neg':
                md += f"### {insight.aspect}\n"
                md += f"- Mentions: {insight.mentions}\n"
                md += f"- Impact: -{insight.damage:.1f} rating points\n"
                md += f"- Confidence: {insight.confidence_label}\n\n"

        return StreamingResponse(
            StringIO(md),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=analysis_{analysis_id}.md"}
        )

    elif format == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['aspect', 'polarity', 'mentions', 'damage', 'pct_negative', 'confidence'])

        for insight in results.insights:
            writer.writerow([
                insight.aspect,
                insight.polarity,
                insight.mentions,
                insight.damage or 0,
                insight.pct_negative,
                insight.confidence_label
            ])

        return StreamingResponse(
            StringIO(output.getvalue()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=analysis_{analysis_id}.csv"}
        )

    else:
        raise HTTPException(status_code=400, detail="Format must be 'markdown' or 'csv'")


@app.post("/api/analyses/{analysis_id}/simulate", response_model=SimulateResponse)
def simulate(analysis_id: str, request: SimulateRequest):
    """
    Run rating impact simulation.
    """
    if analysis_id not in ANALYSES_CACHE:
        raise HTTPException(status_code=404, detail="Analysis not found")

    results = ANALYSES_CACHE[analysis_id]["results"]
    insights = results.insights

    # Calculate impact
    current_avg = results.meta.avg_rating or 0.0
    projected_avg = current_avg
    contributions = {}

    for aspect, fraction in request.fixes.items():
        # Find insight
        insight = next((i for i in insights if i.aspect == aspect and i.polarity == 'neg'), None)
        if insight and insight.damage:
            improvement = abs(insight.damage) * fraction
            projected_avg += improvement
            contributions[aspect] = improvement

    projected_avg = min(5.0, projected_avg)

    return SimulateResponse(
        current_avg=current_avg,
        projected_avg=projected_avg,
        contributions=contributions,
        single_cause_unhappy_count=sum(i.single_cause_unhappy for i in insights),
        confidence_labels={i.aspect: i.confidence_label for i in insights},
        rating_source=results.reviews[0].rating_source if results.reviews else "given",
        caveat="Estimates are associations from your review data, not guaranteed causes. Effects of several fixes are added; interactions are ignored."
    )


# ... existing code ...
@app.delete("/api/analyses/{analysis_id}")
def delete_analysis(analysis_id: str):
    """
    Delete an analysis.
    """
    if analysis_id not in ANALYSES_CACHE:
        raise HTTPException(status_code=404, detail="Analysis not found")

    del ANALYSES_CACHE[analysis_id]
    return {"status": "success"}


@app.get("/api/analyses/{analysis_id}/reviews")
def get_reviews(
    analysis_id: str,
    aspect: Optional[str] = None,
    polarity: Optional[str] = None,
    language: Optional[str] = None,
    cluster: Optional[str] = None
):
    """
    Get reviews for an analysis, filtered by aspect/polarity/language/cluster.
    Returns reviews with clauses highlighted for the selected aspect.
    """
    if analysis_id not in ANALYSES_CACHE:
        raise HTTPException(status_code=404, detail="Analysis not found")

    results = ANALYSES_CACHE[analysis_id]["results"]

    aspect_filter = aspect.lower() if aspect else None
    polarity_filter = polarity.lower() if polarity else None
    language_filter = language.lower() if language else None
    cluster_filter = cluster

    filtered_clauses = [
        clause for clause in results.clauses
        if (not aspect_filter or (clause.aspect and clause.aspect.lower() == aspect_filter))
        and (not polarity_filter or clause.polarity.lower() == polarity_filter)
        and (not cluster_filter or clause.cluster_id == cluster_filter)
    ]

    if language_filter:
        review_ids_for_lang = {
            review.review_id for review in results.reviews
            if review.lang and review.lang.lower() == language_filter
        }
        filtered_clauses = [
            clause for clause in filtered_clauses
            if clause.review_id in review_ids_for_lang
        ]

    review_ids = {clause.review_id for clause in filtered_clauses}

    reviews = []
    for review in results.reviews:
        if review.review_id not in review_ids:
            continue
        if language_filter and (not review.lang or review.lang.lower() != language_filter):
            continue

        review_clauses = [clause for clause in filtered_clauses if clause.review_id == review.review_id]
        text = review.text or ""
        text_lower = text.lower()
        highlights = []

        for clause in review_clauses:
            clause_text = clause.clause_text or ""
            clause_lower = clause_text.lower()
            if not clause_lower:
                continue

            start_index = 0
            while True:
                idx = text_lower.find(clause_lower, start_index)
                if idx < 0:
                    break
                safe_start = max(0, min(len(text), idx))
                safe_end = max(safe_start, min(len(text), idx + len(clause_text)))
                highlights.append({
                    "start": safe_start,
                    "end": safe_end,
                    "aspect": clause.aspect,
                    "polarity": clause.polarity,
                    "score": clause.score,
                })
                start_index = idx + max(1, len(clause_text))

        reviews.append({
            "review_id": review.review_id,
            "text": review.text,
            "rating": review.rating,
            "lang": review.lang,
            "lang_tier": review.lang_tier,
            "lang_confidence": getattr(review, "lang_confidence", 0.0),
            "highlights": highlights,
            "sarcasm_suspect": any(clause.sarcasm_suspect for clause in review_clauses),
            "rating_conflict": any(clause.rating_conflict for clause in review_clauses),
        })

    return {"reviews": reviews}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
