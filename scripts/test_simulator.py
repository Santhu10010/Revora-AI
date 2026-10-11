"""Diagnostic that verifies simulator recovery on a deterministic planted fixture."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.pipeline.analyze import analyze


def build_planted_fixture() -> pd.DataFrame:
    """Build independent observations for each documented synthetic effect."""
    rows = []
    review_number = 0
    rows.extend(
        {
            "review_id": f"synthetic_{review_number + index}",
            "review_text": "Phone is great.",
            "rating": 4.4,
            "version": "fixture",
            "date": "2024-01-01",
        }
        for index in range(60)
    )
    review_number += 60
    effects = [
        ("battery", "Battery life is terrible.", 3.2, 60),
        ("delivery", "Delivery was terrible.", 3.6, 60),
        ("packaging", "Packaging is terrible.", 3.9, 60),
    ]
    for _, (aspect, text, rating, count) in enumerate(effects):
        for _ in range(count):
            rows.append(
                {
                    "review_id": f"synthetic_{review_number}",
                    "review_text": text,
                    "rating": rating,
                    "version": "fixture",
                    "date": "2024-01-01",
                }
            )
            review_number += 1
    return pd.DataFrame(rows)


def run_planted_effects_check():
    """
    Load demo data, run analysis, extract regression coefficients.
    Check if they recover the planted rule:
    - battery negative: -1.2
    - delivery negative: -0.8
    - packaging negative: -0.5
    """
    print("Building deterministic planted fixture...")
    df = build_planted_fixture()
    print(f"Built {len(df)} reviews")

    print("\nRunning analysis...")
    results = analyze(df, mode='lite')

    print(f"\nInsights computed: {len(results.insights)}")

    # Find the relevant insights
    battery_neg = None
    delivery_neg = None
    packaging_neg = None

    for insight in results.insights:
        if insight.aspect == 'battery' and insight.polarity == 'neg':
            battery_neg = insight
        elif insight.aspect == 'delivery' and insight.polarity == 'neg':
            delivery_neg = insight
        elif insight.aspect == 'packaging' and insight.polarity == 'neg':
            packaging_neg = insight

    print("\n" + "="*60)
    print("PLANTED EFFECT RECOVERY TEST")
    print("="*60)

    target_values = {
        'battery': -1.2,
        'delivery': -0.8,
        'packaging': -0.5
    }

    results_dict = {
        'battery': battery_neg,
        'delivery': delivery_neg,
        'packaging': packaging_neg
    }

    tolerance = 0.3
    all_pass = True

    for aspect, target in target_values.items():
        insight = results_dict[aspect]
        if insight is None:
            print(f"\n{aspect.upper()}: NOT FOUND")
            all_pass = False
            continue

        # Use damage as proxy for effect magnitude (mentions * |beta|)
        # Rough estimate: damage / mentions should approximate |beta|
        estimated_effect = -(insight.damage / max(1, insight.mentions))

        print(f"\n{aspect.upper()}:")
        print(f"  Target:        {target:.2f}")
        print(f"  Damage:        {insight.damage:.2f}")
        print(f"  Mentions:      {insight.mentions}")
        print(f"  Est. effect:   {estimated_effect:.2f}")
        print(f"  Beta:          {insight.beta}")
        print(f"  Confidence:    {insight.confidence_label}")

        # Check if close enough
        if insight.beta is not None:
            diff = abs(insight.beta - target)
            passed = diff <= tolerance
            print(f"  Diff:          {diff:.2f} {'PASS' if passed else 'FAIL'}")
            if not passed:
                all_pass = False
        else:
            print(f"  Diff:          N/A (no beta)")
            all_pass = False

    print("\n" + "="*60)
    print(f"Overall: {'PASS' if all_pass else 'FAIL'}")
    print("="*60)

    return all_pass


if __name__ == '__main__':
    passed = run_planted_effects_check()
    raise SystemExit(0 if passed else 1)
    sys.exit(0 if passed else 1)
