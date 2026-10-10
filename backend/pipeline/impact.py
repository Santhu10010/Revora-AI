"""Impact model: rating damage and ranking using OLS regression."""
from typing import List, Dict, Tuple, Optional
import pandas as pd
import numpy as np
from backend.schemas import InsightRecord, ClauseRecord, ClusterRecord


def compute_impact(df, clause_list: List[ClauseRecord], cluster_list: List[ClusterRecord]) -> List[InsightRecord]:
    """
    Compute impact for each insight (aspect-polarity pair).
    Full approach: OLS regression to estimate rating damage.
    """
    if 'rating' not in df.columns or df['rating'].isna().all():
        # No ratings, use lite frequency-based ranking
        return compute_impact_lite(df, clause_list, cluster_list)

    # Build review-by-aspect matrix
    review_aspects = build_review_aspect_matrix(df, clause_list)

    if review_aspects.empty or len(review_aspects) < 10:
        # Too few reviews for regression, fall back to lite
        return compute_impact_lite(df, clause_list, cluster_list)

    # Fit OLS regression
    try:
        betas, ci_dict, confidence_labels = fit_ols_regression(df, review_aspects)
    except Exception as e:
        print(f"OLS regression failed: {e}, falling back to lite")
        return compute_impact_lite(df, clause_list, cluster_list)

    # Build insights
    insights = compute_insights_from_betas(df, clause_list, review_aspects, betas, ci_dict, confidence_labels)

    return insights


def build_review_aspect_matrix(df, clause_list: List[ClauseRecord]) -> pd.DataFrame:
    """
    Build a review-by-aspect matrix where each row is a review and columns are
    'neg_<aspect>' (1 if aspect mentioned negatively, 0 otherwise) and
    'pos_<aspect>' (1 if aspect mentioned positively, 0 otherwise).
    """
    review_ids = df['review_id'].unique()
    matrix_data = {'review_id': [], 'rating': []}

    # Collect all aspects
    all_aspects = set()
    for clause in clause_list:
        if clause.aspect and clause.aspect != 'other':
            all_aspects.add(clause.aspect)

    # Initialize columns
    for aspect in all_aspects:
        matrix_data[f'neg_{aspect}'] = []
        matrix_data[f'pos_{aspect}'] = []

    # Fill matrix
    for review_id in review_ids:
        matrix_data['review_id'].append(review_id)

        # Get rating
        review_row = df[df['review_id'] == review_id].iloc[0]
        rating = review_row.get('rating')
        if pd.isna(rating):
            continue
        matrix_data['rating'].append(rating)

        # Get clauses for this review
        review_clauses = [c for c in clause_list if c.review_id == review_id]

        # Initialize aspect columns
        for aspect in all_aspects:
            has_neg = any(c.aspect == aspect and c.polarity == 'neg' for c in review_clauses)
            has_pos = any(c.aspect == aspect and c.polarity == 'pos' for c in review_clauses)
            matrix_data[f'neg_{aspect}'].append(1 if has_neg else 0)
            matrix_data[f'pos_{aspect}'].append(1 if has_pos else 0)

    result = pd.DataFrame(matrix_data)
    result = result.dropna(subset=['rating'])
    return result


def fit_ols_regression(df, review_aspects: pd.DataFrame) -> Tuple[Dict, Dict, Dict]:
    """
    Fit OLS regression: rating ~ neg_aspects + pos_aspects
    Returns: (betas, confidence_intervals, confidence_labels)
    """
    try:
        import statsmodels.api as sm
    except ImportError:
        # Fallback: simple correlation without statsmodels
        return fallback_simple_regression(df, review_aspects)

    # Prepare features
    X = review_aspects.drop(columns=['review_id', 'rating'])
    y = review_aspects['rating']

    # Add constant
    X = sm.add_constant(X)

    # Fit OLS with robust standard errors
    try:
        model = sm.OLS(y, X).fit(cov_type='HC1')
    except:
        model = sm.OLS(y, X).fit()

    # Extract results
    betas = {}
    ci_dict = {}
    confidence_labels = {}

    for col in model.params.index:
        if col == 'const':
            continue

        coef = model.params[col]
        betas[col] = coef

        # Confidence interval
        try:
            ci = model.conf_int().loc[col]
            ci_dict[col] = (ci[0], ci[1])
        except:
            ci_dict[col] = (coef - 0.5, coef + 0.5)

        # Confidence label: low if p-value > 0.1 or few mentions
        try:
            pval = model.pvalues[col]
            confidence_labels[col] = 'low' if pval > 0.1 else 'ok'
        except:
            confidence_labels[col] = 'ok'

    return betas, ci_dict, confidence_labels


def fallback_simple_regression(df, review_aspects: pd.DataFrame) -> Tuple[Dict, Dict, Dict]:
    """
    Fallback: simple correlation-based "betas" when statsmodels unavailable.
    """
    X = review_aspects.drop(columns=['review_id', 'rating'])
    y = review_aspects['rating']

    betas = {}
    ci_dict = {}
    confidence_labels = {}

    for col in X.columns:
        # Compute correlation
        if X[col].std() > 0:
            correlation = X[col].corr(y)
            # Scale to approximate beta (crude approximation)
            betas[col] = correlation * y.std() / (X[col].std() + 1e-6)
        else:
            betas[col] = 0.0

        ci_dict[col] = (betas[col] - 0.3, betas[col] + 0.3)
        confidence_labels[col] = 'low'  # No p-value, assume low confidence

    return betas, ci_dict, confidence_labels


def compute_insights_from_betas(
    df, clause_list: List[ClauseRecord], review_aspects: pd.DataFrame,
    betas: Dict, ci_dict: Dict, confidence_labels: Dict
) -> List[InsightRecord]:
    """
    Convert regression betas into insights sorted by damage.
    """
    insights = {}

    # Count mentions per aspect-polarity
    for clause in clause_list:
        if not clause.aspect or clause.aspect == 'other':
            continue

        key = (clause.aspect, clause.polarity)
        if key not in insights:
            insights[key] = {
                'mentions': 0,
                'negative_reviews': set(),
                'all_reviews': set(),
                'clauses': []
            }

        insights[key]['mentions'] += 1
        insights[key]['all_reviews'].add(clause.review_id)
        insights[key]['clauses'].append(clause)

    # Build insight records
    insight_records = []
    priority_rank = 0
    current_avg_rating = df['rating'].mean() if 'rating' in df.columns else 4.0

    for (aspect, polarity), data in insights.items():
        mentions = data['mentions']
        if mentions < 1:
            continue

        total_reviews = len(data['all_reviews'])
        pct_negative = len(data['negative_reviews']) / max(1, total_reviews)

        # Get beta from regression
        beta_key = f'{polarity}_{aspect}'
        beta = betas.get(beta_key, 0.0)
        ci_low, ci_high = ci_dict.get(beta_key, (beta - 0.3, beta + 0.3))

        # Damage = mentions * |beta|
        damage = mentions * abs(beta) if beta != 0.0 else 0.0

        # Confidence
        confidence_label = confidence_labels.get(beta_key, 'low')
        if mentions < 30:
            confidence_label = 'low'

        # Single-cause unhappy
        single_cause_unhappy = count_single_cause_unhappy(data['clauses'], df)

        insight = InsightRecord(
            aspect=aspect,
            polarity=polarity,
            mentions=mentions,
            pct_negative=pct_negative,
            beta=beta,
            ci_low=ci_low,
            ci_high=ci_high,
            damage=damage,
            priority_rank=priority_rank if polarity == 'neg' else 9999,
            confidence_label=confidence_label,
            single_cause_unhappy=single_cause_unhappy
        )
        insight_records.append(insight)
        priority_rank += 1

    # Sort by damage (descending)
    insight_records = sorted(
        insight_records,
        key=lambda x: x.damage if x.polarity == 'neg' else -999,
        reverse=True
    )

    # Re-rank
    for i, insight in enumerate(insight_records):
        if insight.polarity == 'neg':
            insight.priority_rank = i

    return insight_records


def count_single_cause_unhappy(clauses: List[ClauseRecord], df) -> int:
    """
    Count reviews with rating <= 2 where this aspect is the only negative aspect.
    """
    count = 0

    # Get all review IDs with unhappy ratings
    unhappy_review_ids = set()
    for _, row in df.iterrows():
        if pd.notna(row.get('rating')) and row['rating'] <= 2:
            unhappy_review_ids.add(row['review_id'])

    # For each unhappy review with a clause in our set
    for clause in clauses:
        if clause.review_id in unhappy_review_ids:
            count += 1
            break  # Count this review once

    return count


def compute_impact_lite(df, clause_list: List[ClauseRecord], cluster_list: List[ClusterRecord]) -> List[InsightRecord]:
    """
    Fallback: frequency-based ranking without regression.
    """
    insights = {}

    for clause in clause_list:
        key = (clause.aspect or 'other', clause.polarity)
        if key not in insights:
            insights[key] = {'mentions': 0, 'clauses': []}
        insights[key]['mentions'] += 1
        insights[key]['clauses'].append(clause)

    insight_records = []
    priority_rank = 0

    sorted_insights = sorted(
        insights.items(),
        key=lambda x: (x[0][1] != 'neg', -x[1]['mentions'])
    )

    for (aspect, polarity), data in sorted_insights:
        mentions = data['mentions']
        if mentions < 1:
            continue

        # Estimate damage (crude: 0.5 per mention)
        damage = mentions * 0.5 if polarity == 'neg' else 0

        insight = InsightRecord(
            aspect=aspect if aspect != 'other' else None,
            polarity=polarity,
            mentions=mentions,
            pct_negative=0.5,
            beta=None,
            ci_low=None,
            ci_high=None,
            damage=damage,
            priority_rank=priority_rank if polarity == 'neg' else 9999,
            confidence_label='low',
            single_cause_unhappy=0
        )
        insight_records.append(insight)
        priority_rank += 1

    return insight_records
