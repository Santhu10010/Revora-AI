from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import ANALYSES_CACHE, app
from backend.pipeline.analyze import analyze

ROOT = Path(__file__).resolve().parent.parent
DEMO_CSV = ROOT / "data" / "demo_hinglish.csv"
client = TestClient(app)


def _seed_demo_analysis(analysis_id: str = "demo_reviews"):
    ANALYSES_CACHE.clear()
    df = pd.read_csv(DEMO_CSV)
    results = analyze(df, mode="lite")
    ANALYSES_CACHE[analysis_id] = {
        "id": analysis_id,
        "filename": DEMO_CSV.name,
        "created_at": "2026-01-01T00:00:00",
        "mode": "lite",
        "results": results,
    }
    return analysis_id, results


def test_get_reviews_found():
    analysis_id, results = _seed_demo_analysis()

    response = client.get(
        f"/api/analyses/{analysis_id}/reviews?aspect=battery&polarity=neg"
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "reviews" in payload
    assert len(payload["reviews"]) > 0

    review = payload["reviews"][0]
    assert "lang_confidence" in review
    assert "highlights" in review
    assert review["highlights"]

    matching_clause = next(
        clause
        for clause in results.clauses
        if clause.review_id == review["review_id"]
        and clause.aspect == "battery"
        and clause.polarity == "neg"
    )
    highlight = next(
        item for item in review["highlights"] if item["aspect"] == "battery"
    )
    assert highlight["start"] < highlight["end"]
    assert review["text"][highlight["start"] : highlight["end"]].lower() == matching_clause.clause_text.lower()


def test_get_reviews_empty_filter():
    analysis_id, _ = _seed_demo_analysis()

    response = client.get(f"/api/analyses/{analysis_id}/reviews?aspect=not_a_real_aspect")

    assert response.status_code == 200, response.text
    assert response.json() == {"reviews": []}


def test_get_reviews_unknown_analysis():
    response = client.get("/api/analyses/unknown_analysis/reviews")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_highlight_correctness():
    analysis_id, results = _seed_demo_analysis()

    response = client.get(f"/api/analyses/{analysis_id}/reviews?aspect=battery&polarity=neg")
    assert response.status_code == 200, response.text

    payload = response.json()
    highlights_checked = 0

    for review in payload["reviews"]:
        review_text = review["text"]
        clauses_for_review = [
            clause
            for clause in results.clauses
            if clause.review_id == review["review_id"]
            and clause.aspect == "battery"
            and clause.polarity == "neg"
        ]
        for highlight in review["highlights"]:
            assert 0 <= highlight["start"] < len(review_text)
            assert highlight["start"] < highlight["end"] <= len(review_text)
            slice_text = review_text[highlight["start"] : highlight["end"]]
            clause = next(
                clause
                for clause in clauses_for_review
                if clause.clause_text.lower() == slice_text.lower()
            )
            assert clause.clause_text.lower() == slice_text.lower()
            highlights_checked += 1

    assert highlights_checked > 0
