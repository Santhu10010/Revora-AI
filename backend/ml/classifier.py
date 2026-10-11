"""Reproducible, CPU-friendly Hinglish sentiment classifier."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from backend.ml.datasets import SentimentExample


DEFAULT_ARTIFACT_DIR = Path("models") / "sentiment" / "hinglish_tfidf"
ARTIFACT_VERSION = "1"


def build_classifier(seed: int = 42, feature_set: str = "word_char") -> Pipeline:
    vectorizers = {
        "word": TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            min_df=2,
            sublinear_tf=True,
            strip_accents="unicode",
        ),
        "char": TfidfVectorizer(
            analyzer="char",
            ngram_range=(3, 5),
            min_df=2,
            sublinear_tf=True,
            max_features=100_000,
        ),
    }
    if feature_set == "word_char":
        features = FeatureUnion(
            [("word", vectorizers["word"]), ("char", vectorizers["char"])]
        )
    elif feature_set in vectorizers:
        features = vectorizers[feature_set]
    else:
        raise ValueError(f"Unsupported feature set: {feature_set}")
    return Pipeline(
        [
            ("features", features),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=seed,
                    solver="liblinear",
                ),
            ),
        ]
    )


def train_classifier(
    examples: list[SentimentExample], seed: int = 42, feature_set: str = "word_char"
) -> Pipeline:
    if not examples:
        raise ValueError("Cannot train on an empty split")
    labels = {example.label for example in examples}
    if labels != {"neg", "neu", "pos"}:
        raise ValueError(f"Training split must contain neg, neu, and pos; found {labels}")
    model = build_classifier(seed, feature_set)
    model.fit([example.text for example in examples], [example.label for example in examples])
    return model


def save_artifact(model: Pipeline, artifact_dir: str | Path, metadata: dict[str, Any]) -> None:
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifact_dir / "model.joblib", compress=3)
    (artifact_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )


def load_artifact(artifact_dir: str | Path) -> Pipeline:
    artifact_dir = Path(artifact_dir)
    model_path = artifact_dir / "model.joblib"
    if not model_path.is_file():
        raise FileNotFoundError(f"Sentiment model artifact not found: {model_path}")
    metadata_path = artifact_dir / "metadata.json"
    if not metadata_path.is_file():
        raise ValueError(f"Sentiment model metadata not found: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    required = {
        "artifact_version",
        "task",
        "source",
        "language",
        "label_map",
        "training_split",
    }
    missing = required.difference(metadata)
    if missing:
        raise ValueError(f"Sentiment model metadata is incomplete: {sorted(missing)}")
    if metadata["artifact_version"] != ARTIFACT_VERSION:
        raise ValueError(f"Unsupported sentiment artifact version: {metadata['artifact_version']}")
    if metadata["language"] != "Hinglish code-mixed":
        raise ValueError(f"Unsupported sentiment model language: {metadata['language']}")
    return joblib.load(model_path)


def predict_texts(model: Pipeline, texts: list[str]) -> list[dict[str, Any]]:
    if not texts:
        return []
    predictions = model.predict(texts)
    probabilities = model.predict_proba(texts)
    classes = list(model.classes_)
    outputs = []
    for label, scores in zip(predictions, probabilities):
        outputs.append(
            {
                "label": str(label),
                "score": float(max(scores)),
                "probabilities": {str(name): float(value) for name, value in zip(classes, scores)},
            }
        )
    return outputs


def configured_artifact_dir() -> Path | None:
    configured = os.getenv("REVORA_SENTIMENT_MODEL")
    return Path(configured) if configured else None
