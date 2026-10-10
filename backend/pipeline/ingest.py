"""Ingestion and validation."""
import pandas as pd
import hashlib
from typing import Tuple


def ingest_and_validate(df: pd.DataFrame) -> Tuple[pd.DataFrame, list]:
    """
    Validate and clean the input DataFrame.

    Returns:
        (cleaned_df, warnings_list)
    """
    warnings = []

    # Check for empty DataFrame
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    # Look for text column (case-insensitive)
    text_col = None
    for col in df.columns:
        if col.lower() in ('review_text', 'text', 'review', 'comment'):
            text_col = col
            break

    if text_col is None:
        # If no recognizable column, use the first column
        if len(df.columns) > 0:
            text_col = df.columns[0]
            warnings.append(f"No 'review_text' column found. Using '{text_col}' as text.")
        else:
            raise ValueError("DataFrame has no columns")

    # Rename text column to standard name
    df = df.rename(columns={text_col: 'review_text'})

    # Standardize optional columns
    df = standardize_columns(df)

    # Drop rows with empty text
    df = df[df['review_text'].notna() & (df['review_text'].str.len() > 0)]
    if df.empty:
        raise ValueError("No reviews with non-empty text after cleaning")

    # Truncate very long reviews
    df['review_text'] = df['review_text'].str[:1000]

    # Clean and validate ratings
    if 'rating' in df.columns:
        df['rating'] = pd.to_numeric(df['rating'], errors='coerce')
        # Coerce ratings to 1-5 range
        invalid_count = (df['rating'].notna() & ((df['rating'] < 1) | (df['rating'] > 5))).sum()
        if invalid_count > 0:
            warnings.append(f"Coerced {invalid_count} out-of-range ratings to 1-5")
        df['rating'] = df['rating'].clip(lower=1, upper=5)

    # Add review_id if not present
    if 'review_id' not in df.columns:
        df.insert(0, 'review_id', [f"review_{i}" for i in range(len(df))])

    # Mark exact duplicates
    df['is_duplicate'] = df['review_text'].duplicated(keep='first')
    dup_count = df['is_duplicate'].sum()
    if dup_count > 0:
        warnings.append(f"Found {dup_count} exact duplicate reviews")

    # Add file hash for demo caching
    df['file_hash'] = compute_file_hash(df)

    # Add placeholders for fields filled later
    for col in ['lang', 'script', 'is_romanized', 'lang_confidence', 'lang_tier',
                'translated_text', 'rating_source']:
        if col not in df.columns:
            df[col] = None if col in ['lang', 'script', 'translated_text'] else (False if col == 'is_romanized' else 0)

    df['rating_source'] = 'given' if 'rating' in df.columns else 'pseudo'
    df['lang_tier'] = 4  # Default to unscored

    return df, warnings


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize optional columns to lowercase names."""
    # Map common column names
    rename_map = {
        'Rating': 'rating',
        'Date': 'date',
        'Version': 'version',
        'Review_ID': 'review_id',
        'ReviewID': 'review_id',
    }
    df = df.rename(columns=rename_map)
    return df


def compute_file_hash(df: pd.DataFrame) -> str:
    """Compute a hash of the DataFrame for caching precomputed results."""
    content = df['review_text'].str.cat(sep='\n')
    return hashlib.sha256(content.encode()).hexdigest()[:16]
