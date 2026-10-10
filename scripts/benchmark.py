"""Benchmark lite vs full mode on a labeled set."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from backend.pipeline.sentiment import score_sentiment
from backend.schemas import ClauseRecord


def run_benchmark():
    """
    Load 100-clause benchmark set, score in both modes, compute accuracy.
    """
    # Load benchmark
    df = pd.read_csv('data/benchmark_clauses.csv')
    print(f"Loaded {len(df)} benchmark clauses")

    # Convert to ClauseRecords
    clauses_lite = []
    clauses_full = []

    for _, row in df.iterrows():
        clause = ClauseRecord(
            review_id='bench',
            clause_id=f"bench_{row.name}",
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
        clauses_lite.append(clause)
        clauses_full.append(clause)

    # Score in both modes
    print("\nScoring lite mode...")
    clauses_lite = score_sentiment(clauses_lite, mode='lite')

    print("Scoring full mode...")
    try:
        clauses_full = score_sentiment(clauses_full, mode='full')
    except Exception as e:
        print(f"Full mode failed (models not available): {e}")
        print("Falling back to lite mode results")
        clauses_full = clauses_lite

    # Compare to ground truth
    print("\n" + "="*60)
    print("BENCHMARK RESULTS")
    print("="*60)

    lite_correct = 0
    full_correct = 0
    english_lite = 0
    english_full = 0
    hinglish_lite = 0
    hinglish_full = 0

    for i, row in df.iterrows():
        true_label = row['label']
        lite_pred = clauses_lite[i].polarity
        full_pred = clauses_full[i].polarity
        lang = row['language']

        if lite_pred == true_label:
            lite_correct += 1
        if full_pred == true_label:
            full_correct += 1

        if lang == 'en':
            if lite_pred == true_label:
                english_lite += 1
            if full_pred == true_label:
                english_full += 1
        else:
            if lite_pred == true_label:
                hinglish_lite += 1
            if full_pred == true_label:
                hinglish_full += 1

    total = len(df)
    english_count = len(df[df['language'] == 'en'])
    hinglish_count = len(df[df['language'] == 'hinglish'])

    print(f"\nOverall accuracy:")
    print(f"  Lite mode:  {lite_correct}/{total} = {100*lite_correct/total:.1f}%")
    print(f"  Full mode:  {full_correct}/{total} = {100*full_correct/total:.1f}%")

    print(f"\nEnglish ({english_count} clauses):")
    print(f"  Lite mode:  {english_lite}/{english_count} = {100*english_lite/max(1,english_count):.1f}%")
    print(f"  Full mode:  {english_full}/{english_count} = {100*english_full/max(1,english_count):.1f}%")

    print(f"\nHinglish ({hinglish_count} clauses):")
    print(f"  Lite mode:  {hinglish_lite}/{hinglish_count} = {100*hinglish_lite/max(1,hinglish_count):.1f}%")
    print(f"  Full mode:  {hinglish_full}/{hinglish_count} = {100*hinglish_full/max(1,hinglish_count):.1f}%")

    print("\n" + "="*60)
    gate_lite = 100*lite_correct/total >= 70
    gate_full = 100*full_correct/total >= 75
    print(f"Gate (lite >= 70%, full >= 75%):")
    print(f"  Lite: {'PASS' if gate_lite else 'FAIL'}")
    print(f"  Full: {'PASS' if gate_full else 'FAIL'}")
    print("="*60)

    return {
        'lite_accuracy': 100*lite_correct/total,
        'full_accuracy': 100*full_correct/total,
        'english_lite': 100*english_lite/max(1,english_count),
        'english_full': 100*english_full/max(1,english_count),
        'hinglish_lite': 100*hinglish_lite/max(1,hinglish_count),
        'hinglish_full': 100*hinglish_full/max(1,hinglish_count),
    }


if __name__ == '__main__':
    results = run_benchmark()
