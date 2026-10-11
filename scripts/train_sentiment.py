"""Train and evaluate the official SemEval Hinglish sentiment classifier."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import json
import platform
import sys

from sklearn.metrics import accuracy_score, confusion_matrix, classification_report, f1_score

# Allow both `python scripts/train_sentiment.py` and `python -m scripts.train_sentiment`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ml.classifier import (
    ARTIFACT_VERSION,
    DEFAULT_ARTIFACT_DIR,
    predict_texts,
    save_artifact,
    train_classifier,
)
from backend.ml.datasets import load_hinglish_split, validate_split_integrity


def evaluate(model, examples):
    outputs = predict_texts(model, [example.text for example in examples])
    actual = [example.label for example in examples]
    predicted = [output["label"] for output in outputs]
    labels = ["neg", "neu", "pos"]
    return {
        "examples": len(examples),
        "accuracy": accuracy_score(actual, predicted),
        "macro_f1": f1_score(actual, predicted, labels=labels, average="macro"),
        "per_class": classification_report(
            actual, predicted, labels=labels, target_names=labels, output_dict=True, zero_division=0
        ),
        "confusion_matrix": confusion_matrix(actual, predicted, labels=labels).tolist(),
        "label_counts": dict(Counter(actual)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=Path("Semeval_2020_task9_data.zip"))
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    splits = {name: load_hinglish_split(args.archive, name) for name in ("train", "validation", "test")}
    validate_split_integrity(splits)
    candidates = {}
    for feature_set in ("word", "char", "word_char"):
        candidate = train_classifier(splits["train"], seed=args.seed, feature_set=feature_set)
        candidates[feature_set] = (candidate, evaluate(candidate, splits["validation"]))
    selected_feature_set, (model, validation_metrics) = max(
        candidates.items(), key=lambda item: item[1][1]["macro_f1"]
    )
    metrics = {name: evaluate(model, splits[name]) for name in ("validation", "test")}
    metadata = {
        "artifact_version": ARTIFACT_VERSION,
        "model_name": "hinglish_tfidf_logistic_regression",
        "task": "three-class sentiment classification",
        "source": "SemEval-2020 Task 9",
        "language": "Hinglish code-mixed",
        "label_map": {"negative": "neg", "neutral": "neu", "positive": "pos"},
        "training_split": "train",
        "evaluation_splits": ["validation", "test"],
        "seed": args.seed,
        "python": sys.version,
        "platform": platform.platform(),
        "hardware": "CPU",
        "feature_set": selected_feature_set,
        "candidate_validation_macro_f1": {
            name: candidate_metrics["macro_f1"]
            for name, (_, candidate_metrics) in candidates.items()
        },
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "metrics": metrics,
    }
    save_artifact(model, args.artifact_dir, metadata)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
