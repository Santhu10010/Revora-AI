"""Precompute demo analysis and cache it."""
import pickle
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.pipeline.analyze import analyze


def precompute_demo():
    """
    Run full analysis on demo_hinglish.csv and save results.
    """
    print("Loading demo data...")
    df = pd.read_csv(ROOT / 'data' / 'demo_hinglish.csv')
    print(f"Loaded {len(df)} reviews")

    print("\nRunning analysis (lite mode)...")
    results = analyze(df, mode='lite')

    print("\nResults:")
    print(f"  Reviews: {results.meta.total_reviews}")
    print(f"  Clauses: {results.meta.total_clauses}")
    print(f"  Clusters: {results.meta.total_clusters}")
    print(f"  Insights: {len(results.insights)}")
    print(f"  Processing time: {results.meta.processing_ms}ms")
    print(f"  Safety cases: {len(results.meta.safety_cases)}")

    # Save results
    cache_file = ROOT / 'data' / 'demo_results.pkl'
    with open(cache_file, 'wb') as f:
        pickle.dump(results, f)
    print(f"\nCached results to {cache_file}")

    # Also save a summary
    summary_file = ROOT / 'data' / 'demo_summary.txt'
    with open(summary_file, 'w') as f:
        f.write(f"Demo Analysis Summary\n")
        f.write(f"====================\n\n")
        f.write(f"Reviews: {results.meta.total_reviews}\n")
        f.write(f"Avg Rating: {results.meta.avg_rating:.2f}\n")
        f.write(f"Negative: {results.meta.pct_negative:.1%}\n")
        f.write(f"Processing Time: {results.meta.processing_ms}ms\n")
        f.write(f"Languages: {results.meta.languages_detected}\n")
        f.write(f"Safety Cases: {len(results.meta.safety_cases)}\n")
        f.write(f"\nTop Issues:\n")
        for i in results.insights[:5]:
            if i.polarity == 'neg':
                f.write(f"  {i.aspect}: {i.mentions} mentions, -{i.damage:.1f} pts\n")

    print(f"Saved summary to {summary_file}")

    return results


if __name__ == '__main__':
    precompute_demo()
