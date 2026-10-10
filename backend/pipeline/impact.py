"""Impact model: rating damage and ranking."""
from typing import List
import pandas as pd
from backend.schemas import InsightRecord, ClauseRecord, ClusterRecord


def compute_impact(df, clause_list: List[ClauseRecord], cluster_list: List[ClusterRecord]) -> List[InsightRecord]:
    """
    Compute impact for each insight (aspect-polarity pair).
    Lite mode: simple frequency ranking without regression.
    Full mode would add OLS regression.
    """
    insights = {}

    # Count mentions per aspect-polarity
    for clause in clause_list:
        key = (clause.aspect or 'other', clause.polarity)
        if key not in insights:
            insights[key] = {
                'mentions': 0,
                'negative_reviews': set(),
                'positive_reviews': set(),
                'all_reviews': set(),
                'clauses': []
            }

        insights[key]['mentions'] += 1
        insights[key]['all_reviews'].add(clause.review_id)
        insights[key]['clauses'].append(clause)

        # Track negative/positive review counts
        review_rating = df[df['review_id'] == clause.review_id]['rating'].values
        if len(review_rating) > 0 and pd.notna(review_rating[0]):
            if review_rating[0] <= 2:
                insights[key]['negative_reviews'].add(clause.review_id)
            elif review_rating[0] >= 4:
                insights[key]['positive_reviews'].add(clause.review_id)

    # Build insight records
    insight_records = []
    priority_rank = 0

    # Sort by mentions (negative first, then positive)
    sorted_insights = sorted(
        insights.items(),
        key=lambda x: (x[0][1] != 'neg', -x[1]['mentions'])
    )

    for (aspect, polarity), data in sorted_insights:
        mentions = data['mentions']

        if mentions < 1:
            continue

        total_reviews = len(data['all_reviews'])
        pct_negative = len(data['negative_reviews']) / max(1, total_reviews)

        # Estimate damage (simplified: assume 0.5 points per negative mention)
        damage = mentions * 0.5 if polarity == 'neg' else 0

        # Confidence label
        confidence_label = 'ok' if mentions >= 30 else 'low'

        # Single-cause unhappy: reviews where this is the only negative aspect
        single_cause_unhappy = count_single_cause_unhappy(data['clauses'], df)

        insight = InsightRecord(
            aspect=aspect if aspect != 'other' else None,
            polarity=polarity,
            mentions=mentions,
            pct_negative=pct_negative,
            beta=None,  # No regression in lite mode
            ci_low=None,
            ci_high=None,
            damage=damage,
            priority_rank=priority_rank if polarity == 'neg' else 9999,
            confidence_label=confidence_label,
            single_cause_unhappy=single_cause_unhappy
        )
        insight_records.append(insight)
        priority_rank += 1

    return insight_records


def count_single_cause_unhappy(clauses: List[ClauseRecord], df) -> int:
    """
    Count reviews with rating <= 2 where this is the only negative aspect.
    """
    count = 0
    unhappy_reviews = {}

    # Find unhappy reviews (rating <= 2)
    for _, row in df.iterrows():
        if pd.notna(row.get('rating')) and row['rating'] <= 2:
            unhappy_reviews[row['review_id']] = []

    # Count negative aspects per unhappy review
    for clause in clauses:
        if clause.review_id in unhappy_reviews:
            unhappy_reviews[clause.review_id].append(clause.polarity)

    # Count reviews where only one aspect is negative
    for review_id, polarities in unhappy_reviews.items():
        neg_count = sum(1 for p in polarities if p == 'neg')
        if neg_count == 1:
            count += 1

    return count
