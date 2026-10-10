"""Test input validation edge cases."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.pipeline.ingest import ingest_and_validate


def test_empty_file():
    df = pd.DataFrame()
    with pytest.raises(ValueError, match='empty'):
        ingest_and_validate(df)


def test_no_text_column():
    df = pd.DataFrame({'rating': [1, 2, 3], 'other_col': ['a', 'b', 'c']})
    with pytest.raises(ValueError, match='No review text column found'):
        ingest_and_validate(df)


def test_no_rating_column():
    df = pd.DataFrame({'review_text': ['great', 'bad', 'ok']})
    result, _ = ingest_and_validate(df)
    assert 'rating' in result.columns
    assert 'rating_source' in result.columns
    assert result['rating_source'].iloc[0] == 'pseudo'
    assert result['rating'].isna().all()


def test_bad_ratings():
    df = pd.DataFrame({'review_text': ['great', 'bad', 'ok'], 'rating': [10, -5, 3]})
    result, warnings = ingest_and_validate(df)
    assert result['rating'].isna().sum() == 2
    assert result['rating'].dropna().between(1, 5).all()
    assert any('out-of-range' in w.lower() for w in warnings)


def test_non_numeric_ratings():
    df = pd.DataFrame({'review_text': ['great', 'bad', 'ok'], 'rating': ['five', '2', 'three']})
    result, warnings = ingest_and_validate(df)
    assert any('non-numeric' in w.lower() for w in warnings)
    assert result['rating'].notna().sum() == 1


def test_empty_text():
    df = pd.DataFrame({'review_text': ['great', '', 'ok', None], 'rating': [5, 4, 3, 2]})
    result, warnings = ingest_and_validate(df)
    assert len(result) == 2
    assert any('empty text' in w.lower() for w in warnings)


def test_duplicates():
    df = pd.DataFrame({'review_text': ['great product', 'great product', 'ok product'], 'rating': [5, 5, 3]})
    result, warnings = ingest_and_validate(df)
    assert result['is_duplicate'].sum() == 1
    assert any('duplicate' in w.lower() for w in warnings)


def test_very_long_review():
    long_text = 'a' * 2000
    df = pd.DataFrame({'review_text': [long_text, 'short'], 'rating': [5, 3]})
    result, _ = ingest_and_validate(df)
    assert len(result.iloc[0]['review_text']) <= 1000


def test_redaction_of_pii():
    df = pd.DataFrame({'review_text': ['Email me at test@example.com', 'Call 9876543210 now'], 'rating': [5, 3]})
    result, _ = ingest_and_validate(df)
    text = ' '.join(result['review_text'].tolist())
    assert '[EMAIL]' in text
    assert '[PHONE]' in text
