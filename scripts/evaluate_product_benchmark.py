"""Evaluate an optional trained artifact on the labeled product-review benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path
import csv
import json

from sklearn.metrics import accuracy_score, classification_report, f1_score

# Allow direct execution from the repository root.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ml.classifier import load_artifact, predict_texts
from backend.pipeline.sentiment import score_sentiment
from backend.schemas import ClauseRecord


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, default=Path("data/benchmark_clauses.csv"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("models/sentiment/hinglish_tfidf"))
    args = parser.parse_args()

    with args.benchmark.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    model = load_artifact(args.artifact_dir)
    actual = [row["label"] for row in rows]
    predicted = [item["label"] for item in predict_texts(model, [row["text"] for row in rows])]
    baseline_clauses = [
        ClauseRecord(
            review_id=str(index),
            clause_id=str(index),
            clause_text=row["text"],
            score=0.0,
            polarity="neu",
            confidence=0.0,
            score_source="lexicon",
        )
        for index, row in enumerate(rows)
    ]
    baseline = score_sentiment(baseline_clauses, mode="lite")
    baseline_predicted = [clause.polarity for clause in baseline]
    print(
        json.dumps(
            {
                "examples": len(rows),
                "sources": sorted({row.get("language", "unknown") for row in rows}),
                "trained_model": {
                    "accuracy": accuracy_score(actual, predicted),
                    "macro_f1": f1_score(actual, predicted, labels=["neg", "neu", "pos"], average="macro"),
                    "per_class": classification_report(
                        actual, predicted, labels=["neg", "neu", "pos"], output_dict=True, zero_division=0
                    ),
                },
                "lite_lexicon": {
                    "accuracy": accuracy_score(actual, baseline_predicted),
                    "macro_f1": f1_score(
                        actual, baseline_predicted, labels=["neg", "neu", "pos"], average="macro"
                    ),
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
