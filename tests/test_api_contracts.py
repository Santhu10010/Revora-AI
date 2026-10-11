from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend import history_store
from backend.main import ANALYSES_CACHE, app
from backend.pipeline.analyze import analyze

ROOT = Path(__file__).resolve().parent.parent
DEMO_CSV = ROOT / "data" / "demo_hinglish.csv"
client = TestClient(app)


def _seed_demo_analysis(analysis_id: str = "demo_contracts"):
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


def test_simulate_endpoint_success():
    analysis_id, results = _seed_demo_analysis()
    insight = next(i for i in results.insights if i.aspect == "battery" and i.polarity == "neg")

    response = client.post(
        f"/api/analyses/{analysis_id}/simulate",
        json={"fixes": {"battery": 0.5}},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["current_avg"] == results.meta.avg_rating
    assert payload["projected_avg"] >= payload["current_avg"]
    assert "battery" in payload["contributions"]
    assert payload["caveat"]
    if results.reviews[0].rating_source == "pseudo":
        assert payload.get("estimate_label") == "sentiment-based estimate"


def test_simulate_endpoint_rejects_bad_aspect_and_fraction():
    analysis_id, _ = _seed_demo_analysis()

    bad_fraction = client.post(f"/api/analyses/{analysis_id}/simulate", json={"fixes": {"battery": 1.7}})
    assert bad_fraction.status_code == 400

    bad_aspect = client.post(f"/api/analyses/{analysis_id}/simulate", json={"fixes": {"not_real": 0.5}})
    assert bad_aspect.status_code == 400


def test_delete_analysis_endpoint():
    analysis_id, _ = _seed_demo_analysis()

    response = client.delete(f"/api/analyses/{analysis_id}")
    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    assert analysis_id not in ANALYSES_CACHE

    missing = client.delete("/api/analyses/unknown_analysis")
    assert missing.status_code == 404


def test_actions_endpoint_and_routing():
    analysis_id, results = _seed_demo_analysis()
    insight = next(i for i in results.insights if i.aspect == "battery" and i.polarity == "neg")

    response = client.post(
        f"/api/analyses/{analysis_id}/actions",
        json={"aspect": "battery", "polarity": "neg"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["team"] == "Product/Engineering"
    assert payload["priority"] == "P2"
    assert payload["estimated_rating_uplift"] >= 0
    assert payload["reply_drafts"]["english"]
    assert payload["reply_drafts"]["hinglish"]


def test_export_analysis_returns_file_response():
    analysis_id, _ = _seed_demo_analysis()

    md = client.get(f"/api/analyses/{analysis_id}/export?format=md")
    assert md.status_code == 200
    assert md.headers["content-type"].startswith("text/markdown")
    assert "attachment; filename=analysis_demo_contracts.md" in md.headers["content-disposition"]

    csv_response = client.get(f"/api/analyses/{analysis_id}/export?format=csv")
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=analysis_demo_contracts.csv" in csv_response.headers["content-disposition"]

    bad = client.get(f"/api/analyses/{analysis_id}/export?format=txt")
    assert bad.status_code == 400


def test_top_issue_pct_negative_not_all_zero():
    analysis_id, results = _seed_demo_analysis()
    response = client.get(f"/api/analyses/{analysis_id}")
    payload = response.json()
    negatives = [issue["pct_negative"] for issue in payload["top_issues"]]
    assert negatives
    assert all(0 <= value <= 1 for value in negatives)
    assert any(value > 0 for value in negatives)


def test_full_mode_falls_back_to_lexicon_without_optional_model():
    df = pd.read_csv(DEMO_CSV)
    results = analyze(df, mode="full")

    assert results.meta.total_reviews == 299
    assert results.meta.pct_negative > 0
    assert any(insight.polarity == "neg" for insight in results.insights)


def test_upload_honors_full_mode_form_field():
    with DEMO_CSV.open("rb") as handle:
        response = client.post(
            "/api/analyze",
            files={"file": ("demo_hinglish.csv", handle, "text/csv")},
            data={"mode": "full"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mode"] == "full"
    assert payload["review_count"] == 299
    assert payload["pct_negative"] > 0
    assert payload["top_issues"]


def test_get_analysis_list_shapes():
    analysis_id, _ = _seed_demo_analysis()
    list_response = client.get("/api/analyses")
    assert list_response.status_code == 200
    assert analysis_id in {item["id"] for item in list_response.json()["analyses"]}

    detail = client.get(f"/api/analyses/{analysis_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert "rating_source" in payload
    assert "warnings" in payload
    assert "languages" in payload
    assert "safety_alerts" in payload


def test_model_status_reports_safe_default(monkeypatch):
    monkeypatch.delenv("REVORA_SENTIMENT_MODEL", raising=False)
    response = client.get("/api/model-status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["active"] is False
    assert payload["model_name"] == "lite_lexicon"


def test_analysis_survives_cache_reload(tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "DB_PATH", tmp_path / "history.sqlite3")
    history_store.initialize()
    analysis_id, results = _seed_demo_analysis("persistent_analysis")
    entry = ANALYSES_CACHE[analysis_id]
    history_store.save(entry)

    ANALYSES_CACHE.clear()
    response = client.get(f"/api/analyses/{analysis_id}")

    assert response.status_code == 200
    assert response.json()["analysis_id"] == analysis_id
    assert response.json()["review_count"] == results.meta.total_reviews

    delete_response = client.delete(f"/api/analyses/{analysis_id}")
    assert delete_response.status_code == 200
    assert history_store.get(analysis_id) is None
