from pathlib import Path

import pandas as pd
import pytest

from backend.ml.classifier import load_artifact, predict_texts, train_classifier
from backend.ml.datasets import SentimentExample, load_hinglish_split, validate_split_integrity
from backend.pipeline.analyze import analyze
from backend.pipeline import sentiment


ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "Semeval_2020_task9_data.zip"


def test_official_hinglish_splits_have_expected_sizes_and_labels():
    if not ARCHIVE.exists():
        pytest.skip("Supplied SemEval archive is not present")
    splits = {name: load_hinglish_split(ARCHIVE, name) for name in ("train", "validation", "test")}
    assert {name: len(rows) for name, rows in splits.items()} == {
        "train": 14000,
        "validation": 3000,
        "test": 3000,
    }
    assert {row.label for row in splits["train"]} == {"neg", "neu", "pos"}
    validate_split_integrity(splits)


def test_split_integrity_rejects_evaluation_leakage():
    with pytest.raises(ValueError, match="leakage"):
        validate_split_integrity(
            {
                "train": [SentimentExample("same", "good", "pos")],
                "test": [SentimentExample("same", "bad", "neg")],
            }
        )


def test_loader_rejects_unknown_split():
    with pytest.raises(ValueError, match="Unsupported split"):
        load_hinglish_split(ARCHIVE, "unknown")


def test_loader_rejects_missing_archive(tmp_path):
    with pytest.raises(FileNotFoundError, match="Dataset archive not found"):
        load_hinglish_split(tmp_path / "missing.zip", "train")


def test_training_prediction_schema_and_save_load(tmp_path):
    examples = [
        SentimentExample("1", "battery is excellent", "pos"),
        SentimentExample("2", "delivery is terrible", "neg"),
        SentimentExample("3", "the phone is okay", "neu"),
    ] * 2
    model = train_classifier(examples)
    outputs = predict_texts(model, ["excellent battery"])
    assert set(outputs[0]) == {"label", "score", "probabilities"}
    assert outputs[0]["label"] in {"neg", "neu", "pos"}
    from backend.ml.classifier import save_artifact

    save_artifact(
        model,
        tmp_path,
        {
            "artifact_version": "1",
            "task": "three-class sentiment classification",
            "source": "test",
            "language": "Hinglish code-mixed",
            "label_map": {"negative": "neg", "neutral": "neu", "positive": "pos"},
            "training_split": "train",
        },
    )
    loaded = load_artifact(tmp_path)
    assert predict_texts(loaded, ["terrible delivery"])[0]["label"] in {"neg", "neu", "pos"}


def test_trained_model_integrates_with_full_analysis(tmp_path, monkeypatch):
    examples = [
        SentimentExample("1", "battery is excellent", "pos"),
        SentimentExample("2", "delivery is terrible", "neg"),
        SentimentExample("3", "the phone is okay", "neu"),
    ] * 2
    model = train_classifier(examples)
    from backend.ml.classifier import save_artifact

    save_artifact(
        model,
        tmp_path,
        {
            "artifact_version": "1",
            "task": "three-class sentiment classification",
            "source": "test",
            "language": "Hinglish code-mixed",
            "label_map": {"negative": "neg", "neutral": "neu", "positive": "pos"},
            "training_split": "train",
        },
    )
    monkeypatch.setenv("REVORA_SENTIMENT_MODEL", str(tmp_path))
    monkeypatch.setattr(sentiment, "TRAINED_MODEL", None)
    results = analyze(
        pd.DataFrame({"review_text": ["battery is excellent", "delivery is terrible"]}),
        mode="full",
    )
    assert results.clauses
    assert all(clause.score_source == "trained" for clause in results.clauses)
