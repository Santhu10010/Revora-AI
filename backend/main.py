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
from backend.schemas import AnalysisResults

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
                df = pd.read_csv(BytesIO(content), encoding='utf-8')
            else:
                df = pd.read_excel(BytesIO(content))
        except UnicodeDecodeError:
            # Try with different encoding
            df = pd.read_csv(BytesIO(content), encoding='latin-1')
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

        # Check upload size limits
        max_rows = 2000 if mode == 'lite' else 5000
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
                    "pct_negative": i.pct_negative,
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
        "pct_negative": results.meta.pct_negative,
        "languages": results.meta.languages_detected,
        "top_issues": [
            {
                "aspect": i.aspect,
                "polarity": i.polarity,
                "mentions": i.mentions,
                "damage": i.damage
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

        return {"format": "markdown", "content": md}

    elif format == "csv":
        import csv
        from io import StringIO

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

        return {"format": "csv", "content": output.getvalue()}

    else:
        raise HTTPException(status_code=400, detail="Format must be 'markdown' or 'csv'")
    """
    Get reviews for an analysis, filtered by aspect/polarity.
    Returns reviews with clauses highlighted for the aspect.
    """
    if analysis_id not in ANALYSES_CACHE:
        raise HTTPException(status_code=404, detail="Analysis not found")

    results = ANALYSES_CACHE[analysis_id]["results"]

    # Filter clauses by aspect and polarity
    filtered_clauses = [
        c for c in results.clauses
        if (not aspect or c.aspect == aspect) and (not polarity or c.polarity == polarity)
    ]

    # Get unique review IDs
    review_ids = set(c.review_id for c in filtered_clauses)

    # Build response
    reviews = []
    for review in results.reviews:
        if review.review_id not in review_ids:
            continue

        # Get clauses for this review
        clauses = [c for c in filtered_clauses if c.review_id == review.review_id]

        # Find highlighted spans
        text = review.text
        highlights = []
        for clause in clauses:
            idx = text.lower().find(clause.clause_text.lower())
            if idx >= 0:
                highlights.append({
                    "start": idx,
                    "end": idx + len(clause.clause_text),
                    "aspect": clause.aspect,
                    "polarity": clause.polarity,
                    "score": clause.score
                })

        reviews.append({
            "review_id": review.review_id,
            "text": review.text,
            "rating": review.rating,
            "lang": review.lang,
            "lang_tier": review.lang_tier,
            "highlights": highlights
        })

    return {"reviews": reviews}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
