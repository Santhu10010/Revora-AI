"""Pipeline orchestration: entry point for analysis."""
import os
from typing import Tuple
import pandas as pd
import time
from datetime import datetime, timezone

from backend.schemas import AnalysisResults, AnalysisMetadata, ReviewRecord
from backend.pipeline import ingest, normalize, language, clauses, aspects, sentiment, safety, cluster, impact


def analyze(df: pd.DataFrame, mode: str = "lite") -> AnalysisResults:
    """
    Main analysis pipeline.

    Args:
        df: Input DataFrame with at least 'review_text' column
        mode: 'lite' or 'full'

    Returns:
        AnalysisResults with reviews, clauses, clusters, insights tables and metadata
    """
    start_time = time.time()

    # Phase 1: Ingest and validate
    df_clean, warnings = ingest.ingest_and_validate(df)
    if df_clean.empty:
        raise ValueError("No valid reviews after ingestion")

    # Phase 2: Normalize
    df_clean = normalize.normalize_reviews(df_clean)

    # Phase 3: Language and script detection
    df_clean = language.detect_language_and_script(df_clean)

    # Phase 4: Clause splitting
    clause_list = clauses.split_clauses(df_clean)

    # Phase 5: Aspect tagging
    clause_list = aspects.tag_aspects(clause_list, mode)

    # Phase 6: Sentiment scoring
    clause_list = sentiment.score_sentiment(clause_list, mode)

    # Phase 7: Safety scanning
    clause_list = safety.scan_safety(clause_list, mode)

    # Phase 8: Clustering
    cluster_list, clause_list = cluster.cluster_clauses(clause_list, mode)

    # Phase 9: Impact and ranking
    insight_list = impact.compute_impact(df_clean, clause_list, cluster_list)

    # Build results
    processing_ms = int((time.time() - start_time) * 1000)

    # Convert to schema records
    review_records = []
    for _, row in df_clean.iterrows():
        review_dict = row.to_dict()
        # Rename review_text to text for schema
        review_dict['text'] = review_dict.pop('review_text', '')
        review_records.append(ReviewRecord(**review_dict))

    # Build metadata
    avg_rating = df_clean['rating'].mean() if 'rating' in df_clean.columns else None
    if pd.isna(avg_rating):
        avg_rating = None

    meta = AnalysisMetadata(
        mode=mode,
        total_reviews=len(df_clean),
        total_clauses=len(clause_list),
        total_clusters=len(cluster_list),
        reviews_with_rating=int((df_clean['rating'].notna()).sum()),
        avg_rating=avg_rating,
        pct_negative=compute_pct_negative(clause_list),
        warnings=warnings,
        processing_ms=processing_ms,
        languages_detected=count_languages(df_clean),
        safety_cases=extract_safety_cases(clause_list),
        timestamp=datetime.now(timezone.utc)
    )

    return AnalysisResults(
        reviews=review_records,
        clauses=clause_list,
        clusters=cluster_list,
        insights=insight_list,
        meta=meta
    )


def compute_pct_negative(clause_list) -> float:
    """Compute percentage of clauses with negative polarity."""
    if not clause_list:
        return 0.0
    neg_count = sum(1 for c in clause_list if c.polarity == 'neg')
    return neg_count / len(clause_list)


def count_languages(df) -> dict:
    """Count detected languages in the review set."""
    if 'lang' not in df.columns:
        return {}
    return df['lang'].value_counts().to_dict()


def extract_safety_cases(clause_list) -> list:
    """Extract high and critical safety cases."""
    safety_cases = []
    for clause in clause_list:
        if clause.safety_tier in ('high', 'critical'):
            safety_cases.append({
                'review_id': clause.review_id,
                'clause_id': clause.clause_id,
                'text': clause.clause_text,
                'tier': clause.safety_tier
            })
    return safety_cases
