"""Ingestion and validation."""
import hashlib
import re
from typing import Tuple

import pandas as pd


def ingest_and_validate(df: pd.DataFrame) -> Tuple[pd.DataFrame, list]:
    """
    Validate and clean the input DataFrame.

    Returns:
        (cleaned_df, warnings_list)
    """
    warnings = []

    if df.empty:
        raise ValueError("Input DataFrame is empty")

    text_col = _detect_text_column(df)
    if text_col is None:
        raise ValueError(
            "No review text column found. Available columns: "
            + ", ".join(str(col) for col in df.columns)
        )

    df = df.rename(columns={text_col: 'review_text'})
    df = standardize_columns(df)

    # Normalize and trim review text.
    df['review_text'] = df['review_text'].fillna('').astype(str).str.strip()
    original_len = len(df)
    df = df[df['review_text'] != '']
    empty_rows = original_len - len(df)
    if empty_rows > 0:
        warnings.append(f"Dropped {empty_rows} empty text rows")

    if df.empty:
        raise ValueError("No reviews with non-empty text after cleaning")

    df['review_text'] = df['review_text'].str[:1000]

    if 'rating' not in df.columns:
        df['rating'] = float('nan')
        df['rating_source'] = 'pseudo'
    else:
        rating_series = pd.to_numeric(df['rating'], errors='coerce')
        non_numeric_count = int(((df['rating'].astype(str).str.strip() != '') & rating_series.isna()).sum())
        if non_numeric_count > 0:
            warnings.append(f"Coerced {non_numeric_count} non-numeric ratings to NaN")

        out_of_range = rating_series.notna() & ((rating_series < 1) | (rating_series > 5))
        out_of_range_count = int(out_of_range.sum())
        if out_of_range_count > 0:
            warnings.append(f"Dropped {out_of_range_count} out-of-range ratings")

        df['rating'] = rating_series.where(rating_series.between(1, 5), pd.NA)
        df['rating_source'] = 'given'

    df['review_text'] = df['review_text'].apply(_redact_pii)

    if 'review_id' not in df.columns:
        df.insert(0, 'review_id', [f"review_{i}" for i in range(len(df))])

    df['is_duplicate'] = df['review_text'].duplicated(keep='first')
    dup_count = int(df['is_duplicate'].sum())
    if dup_count > 0:
        warnings.append(f"Found {dup_count} exact duplicate reviews")

    df['file_hash'] = compute_file_hash(df)

    for col in ['lang', 'script', 'is_romanized', 'lang_confidence', 'lang_tier', 'translated_text']:
        if col not in df.columns:
            if col in ['lang', 'script', 'translated_text', 'lang_confidence']:
                df[col] = None
            elif col == 'is_romanized':
                df[col] = False
            else:
                df[col] = 0

    df['lang_tier'] = 4

    return df, warnings


def _detect_text_column(df: pd.DataFrame):
    for col in df.columns:
        if str(col).strip().lower() in {'review_text', 'review', 'text', 'comment'}:
            return col
    return None


def _redact_pii(text):
    if not isinstance(text, str):
        return text
    text = re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[EMAIL]', text)
    text = re.sub(r'\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b', '[PHONE]', text)
    return text


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize optional columns to lowercase names."""
    rename_map = {
        'Rating': 'rating',
        'Date': 'date',
        'Version': 'version',
        'Review_ID': 'review_id',
        'ReviewID': 'review_id',
    }
    return df.rename(columns=rename_map)


def compute_file_hash(df: pd.DataFrame) -> str:
    """Compute a hash of the DataFrame for caching precomputed results."""
    content = df['review_text'].str.cat(sep='\n')
    return hashlib.sha256(content.encode()).hexdigest()[:16]
