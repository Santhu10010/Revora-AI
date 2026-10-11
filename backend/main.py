"""FastAPI backend for Revora AI."""
import csv
import hashlib
import json
import os
import traceback
from io import BytesIO, StringIO
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

import pandas as pd
import uvicorn
import yaml
from fastapi import FastAPI, File, Form, HTTPException, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from backend.pipeline.analyze import analyze
from backend.ml.classifier import configured_artifact_dir
from backend.schemas import ActionRequest, AnalysisResults, SimulateRequest, SimulateResponse
from backend import history_store

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

# Local cache backed by SQLite so history survives process restarts.
history_store.initialize()
ANALYSES_CACHE = {entry["id"]: entry for entry in history_store.list_all()}

# Mode
APP_MODE = os.getenv("APP_MODE", "lite")
BASE_DIR = Path(__file__).resolve().parent


def _get_analysis(analysis_id: str):
    entry = ANALYSES_CACHE.get(analysis_id)
    if entry is None:
        entry = history_store.get(analysis_id)
        if entry is not None:
            ANALYSES_CACHE[analysis_id] = entry
    return entry


def _all_analyses():
    entries = {entry["id"]: entry for entry in history_store.list_all()}
    entries.update(ANALYSES_CACHE)
    return sorted(entries.values(), key=lambda entry: entry["created_at"], reverse=True)


def _load_routing():
    routing_path = BASE_DIR / "config" / "routing.yaml"
    with routing_path.open("r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    return payload.get("routing", {})


def _route_for_aspect(aspect: str):
    routing = _load_routing()
    if not aspect:
        return ("Product", "P2")
    entry = routing.get(aspect.lower(), {})
    if not entry:
        return ("Product", "P2")
    return (entry.get("team", "Product"), entry.get("priority", "P2"))


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "mode": APP_MODE,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/model-status")
def model_status():
    """Report the explicitly configured sentiment model without exposing paths."""
    artifact_dir = configured_artifact_dir()
    if artifact_dir is None:
        return {
            "active": False,
            "model_name": "lite_lexicon",
            "language": "general fallback",
            "message": "Using the built-in lexicon sentiment scorer.",
        }
    metadata_path = artifact_dir / "metadata.json"
    if not metadata_path.is_file():
        return {
            "active": False,
            "model_name": "lite_lexicon",
            "language": "general fallback",
            "message": "Configured trained model metadata is unavailable; using the built-in scorer.",
        }
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "active": False,
            "model_name": "lite_lexicon",
            "language": "general fallback",
            "message": "Configured trained model metadata is invalid; using the built-in scorer.",
        }
    return {
        "active": True,
        "model_name": metadata.get("model_name", "trained_sentiment"),
        "language": metadata.get("language", "unknown"),
        "message": "Full mode uses the configured trained sentiment model.",
    }


@app.post("/api/analyze")
async def analyze_upload(
    file: UploadFile = File(...),
    mode: Optional[str] = Form(None)
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
        analysis_id = f"analysis_{file_hash}_{int(datetime.now(timezone.utc).timestamp())}"

        entry = {
            "id": analysis_id,
            "filename": file.filename,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "results": results
        }
        history_store.save(entry)
        ANALYSES_CACHE[analysis_id] = entry

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
            for v in _all_analyses()
        ]
    }


@app.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    """Retrieve saved analysis summary."""
    cache_entry = _get_analysis(analysis_id)
    if cache_entry is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

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
        "processing_ms": results.meta.processing_ms,
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
def generate_actions(analysis_id: str, aspect: Optional[str] = None, polarity: Optional[str] = None, request: Optional[ActionRequest] = None):
    """Generate a ticket and reply draft for an issue."""
    cache_entry = _get_analysis(analysis_id)
    if cache_entry is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if request is not None:
        aspect = request.aspect or aspect
        polarity = request.polarity or polarity

    if not aspect or not polarity:
        raise HTTPException(status_code=400, detail="Request body must include both 'aspect' and 'polarity'.")

    results = cache_entry["results"]
    insight = next((i for i in results.insights if i.aspect == aspect and i.polarity == polarity), None)
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    evidence_clauses = [
        c for c in results.clauses
        if c.aspect == aspect and c.polarity == polarity
    ][:5]

    evidence_reviews = []
    for clause in evidence_clauses:
        review = next((r for r in results.reviews if r.review_id == clause.review_id), None)
        if review:
            evidence_reviews.append({
                "review_id": review.review_id,
                "text": clause.clause_text,
                "rating": review.rating,
            })

    team, priority = _route_for_aspect(aspect)
    if aspect.lower() == 'safety':
        team = 'QA/Compliance'
        priority = 'P0'

    template_dir = BASE_DIR / "templates"
    try:
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(template_dir)))
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
            evidence=evidence_reviews,
        )
        reply = reply_template.render(aspect=aspect)
    except Exception:
        raise

    summary = (
        f"{insight.mentions} customer mentions flagged {aspect} with {insight.pct_negative:.1%} negative sentiment. "
        f"Estimated uplift: +{(insight.damage or 0):.2f} rating points."
    )
    return {
        "title": f"{aspect.title()} issue ({polarity.upper()})",
        "team": team,
        "priority": priority,
        "summary": summary,
        "estimated_rating_uplift": float(insight.damage or 0.0),
        "evidence": evidence_reviews,
        "next_steps": [
            f"Review the {aspect} feedback pattern across customer reports.",
            "Confirm the root cause with engineering and QA before shipping a fix.",
            "Track the reduction in negative mentions as the success metric for the next release.",
        ],
        "success_metric": f"Reduce negative {aspect} mentions by 50% in the next 30 days.",
        "reply_drafts": {
            "english": reply,
            "hinglish": reply,
        },
        "ticket": ticket,
        "reply": reply,
    }


@app.get("/api/analyses/{analysis_id}/export")
def export_analysis(analysis_id: str, format: str = "md"):
    """Export analysis results as Markdown or CSV."""
    cache_entry = _get_analysis(analysis_id)
    if cache_entry is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    results = cache_entry["results"]
    fmt = format.lower()
    fmt = "md" if fmt == "markdown" else fmt
    fmt = "md" if fmt == "md" else fmt

    if fmt == "csv":
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
                insight.confidence_label,
            ])
        content = output.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=analysis_{analysis_id}.csv"},
        )

    if fmt in {"md", "markdown"}:
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
            iter([md]),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=analysis_{analysis_id}.md"},
        )

    raise HTTPException(status_code=400, detail="Format must be 'csv' or 'md'.")


@app.post("/api/analyses/{analysis_id}/simulate", response_model=SimulateResponse)
def simulate(analysis_id: str, request: SimulateRequest):
    """Run rating impact simulation."""
    cache_entry = _get_analysis(analysis_id)
    if cache_entry is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    results = cache_entry["results"]
    current_avg = results.meta.avg_rating or 0.0
    projected_avg = current_avg
    contributions = {}

    for aspect, fraction in request.fixes.items():
        if not 0.0 <= float(fraction) <= 1.0:
            raise HTTPException(status_code=400, detail=f"Fix fraction for {aspect} must be between 0 and 1.")
        insight = next((i for i in results.insights if i.aspect == aspect and i.polarity == 'neg'), None)
        if insight is None:
            raise HTTPException(status_code=400, detail=f"Aspect '{aspect}' is not present in this analysis.")
        if insight.damage:
            improvement = abs(insight.damage) * float(fraction)
            projected_avg += improvement
            contributions[aspect] = improvement

    projected_avg = min(5.0, projected_avg)
    estimate_label = "sentiment-based estimate" if results.reviews and results.reviews[0].rating_source == "pseudo" else None
    return SimulateResponse(
        current_avg=current_avg,
        projected_avg=projected_avg,
        contributions=contributions,
        single_cause_unhappy_count=sum(i.single_cause_unhappy for i in results.insights),
        confidence_labels={i.aspect: i.confidence_label for i in results.insights},
        rating_source=results.reviews[0].rating_source if results.reviews else "given",
        caveat="Estimates are associations from your review data, not guaranteed causes. Effects of several fixes are added; interactions are ignored.",
        estimate_label=estimate_label,
    )


@app.delete("/api/analyses/{analysis_id}")
def delete_analysis(analysis_id: str):
    """Delete an analysis."""
    cache_entry = _get_analysis(analysis_id)
    if cache_entry is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    ANALYSES_CACHE.pop(analysis_id, None)
    history_store.delete(analysis_id)
    return {"status": "success"}


@app.get("/api/analyses/{analysis_id}/reviews")
def get_reviews(
    analysis_id: str,
    aspect: Optional[str] = None,
    polarity: Optional[str] = None,
    language: Optional[str] = None,
    cluster: Optional[str] = None,
):
    """Get reviews for an analysis, filtered by aspect/polarity/language/cluster."""
    cache_entry = _get_analysis(analysis_id)
    if cache_entry is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    results = cache_entry["results"]
    aspect_filter = aspect.lower() if aspect else None
    polarity_filter = polarity.lower() if polarity else None
    language_filter = language.lower() if language else None
    cluster_filter = cluster

    filtered_clauses = [
        clause for clause in results.clauses
        if (not aspect_filter or (clause.aspect and clause.aspect.lower() == aspect_filter))
        and (not polarity_filter or (clause.polarity and clause.polarity.lower() == polarity_filter))
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
