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


@app.get("/api/analyses/{analysis_id}/reviews")
def get_analysis_reviews(analysis_id: str, aspect: Optional[str] = None, polarity: Optional[str] = None):
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
