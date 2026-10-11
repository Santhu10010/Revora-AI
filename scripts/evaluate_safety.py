"""Evaluate safety detection recall and precision."""
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.pipeline.safety import scan_safety
from backend.schemas import ClauseRecord


def evaluate_safety():
    """
    Load 40-sentence safety test set, run through safety scanner,
    compute recall and precision.
    """
    print("Loading safety test set...")
    df = pd.read_csv(ROOT / 'data' / 'safety_test_set.csv')
    print(f"Loaded {len(df)} test cases")

    # Convert to ClauseRecords
    clauses = []
    for _, row in df.iterrows():
        clause = ClauseRecord(
            review_id='test',
            clause_id=f"test_{row.name}",
            clause_text=row['text'],
            aspect=None,
            score=0.0,
            polarity='neu',
            confidence=0.0,
            score_source='unscored',
            sarcasm_suspect=False,
            rating_conflict=False,
            safety_tier='none',
            cluster_id=None
        )
        clauses.append(clause)

    # Scan for safety
    print("\nScanning for safety hazards...")
    clauses = scan_safety(clauses, mode='lite')

    # Evaluate
    print("\n" + "="*60)
    print("SAFETY DETECTION EVALUATION")
    print("="*60)

    # Build confusion matrix per tier
    tiers = ['none', 'medium', 'high', 'critical']
    tp = {tier: 0 for tier in tiers}
    fp = {tier: 0 for tier in tiers}
    fn = {tier: 0 for tier in tiers}

    for i, row in df.iterrows():
        expected = row['expected_tier']
        predicted = clauses[i].safety_tier

        # Convert 'none' to higher tiers for evaluation
        expected_level = tier_to_level(expected)
        predicted_level = tier_to_level(predicted)

        if expected == 'none':
            if predicted == 'none':
                pass  # True negative (not counted in recall/precision)
            else:
                fp[predicted] += 1  # False positive
        else:
            if predicted == expected:
                tp[expected] += 1  # True positive
            elif predicted == 'none':
                fn[expected] += 1  # False negative
            else:
                fp[predicted] += 1  # False positive (wrong tier)

    # Compute metrics
    print("\nPer-tier breakdown:")
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for tier in ['critical', 'high', 'medium']:
        t_tp = tp[tier]
        t_fp = fp[tier]
        t_fn = fn[tier]

        recall = t_tp / max(1, t_tp + t_fn)
        precision = t_tp / max(1, t_tp + t_fp)

        total_tp += t_tp
        total_fp += t_fp
        total_fn += t_fn

        print(f"\n{tier.upper()}:")
        print(f"  TP: {t_tp}, FP: {t_fp}, FN: {t_fn}")
        print(f"  Recall:    {100*recall:.1f}%")
        print(f"  Precision: {100*precision:.1f}%")

    # Overall
    overall_recall = total_tp / max(1, total_tp + total_fn)
    overall_precision = total_tp / max(1, total_tp + total_fp)

    print("\n" + "="*60)
    print("OVERALL METRICS")
    print("="*60)
    print(f"True Positives:  {total_tp}")
    print(f"False Positives: {total_fp}")
    print(f"False Negatives: {total_fn}")
    print(f"\nRecall:    {100*overall_recall:.1f}% (target: >= 90%)")
    print(f"Precision: {100*overall_precision:.1f}% (target: >= 80%)")

    gate_pass = overall_recall >= 0.90 and overall_precision >= 0.80
    print(f"\nGate: {'PASS' if gate_pass else 'FAIL'}")
    print("="*60)

    # Show misclassifications
    print("\nMisclassifications:")
    miscount = 0
    for i, row in df.iterrows():
        expected = row['expected_tier']
        predicted = clauses[i].safety_tier
        if expected != predicted:
            miscount += 1
            if miscount <= 10:
                print(f"  {row['text'][:50]} -> expected={expected}, got={predicted}")
    if miscount > 10:
        print(f"  ... and {miscount - 10} more")

    return gate_pass


def tier_to_level(tier: str) -> int:
    """Convert tier name to numeric level for comparison."""
    levels = {'none': 0, 'medium': 1, 'high': 2, 'critical': 3}
    return levels.get(tier, 0)


if __name__ == '__main__':
    passed = evaluate_safety()
    sys.exit(0 if passed else 1)
