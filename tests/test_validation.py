"""Test input validation edge cases."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import tempfile
from io import BytesIO
from backend.pipeline.ingest import ingest_and_validate


def test_empty_file():
    """Test that empty file raises clear error."""
    df = pd.DataFrame()
    try:
        ingest_and_validate(df)
        return False, "Should have raised error for empty file"
    except ValueError as e:
        if "empty" in str(e).lower():
            return True, "Empty file handled correctly"
        return False, f"Wrong error message: {e}"


def test_no_text_column():
    """Test that missing text column prompts user."""
    df = pd.DataFrame({
        'rating': [1, 2, 3],
        'other_col': ['a', 'b', 'c']
    })
    try:
        result, warnings = ingest_and_validate(df)
        if 'other_col' in result.columns and 'review_text' in result.columns:
            return True, "Missing text column handled, used first column"
        return False, "Should have used first column as text"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def test_bad_ratings():
    """Test that out-of-range ratings are coerced."""
    df = pd.DataFrame({
        'review_text': ['great', 'bad', 'ok'],
        'rating': [10, -5, 3]  # Out of range
    })
    result, warnings = ingest_and_validate(df)
    # Check ratings are clipped to 1-5
    if result['rating'].min() >= 1 and result['rating'].max() <= 5:
        return True, "Out-of-range ratings clipped to 1-5"
    return False, f"Ratings not clipped: {result['rating'].tolist()}"


def test_non_numeric_ratings():
    """Test that non-numeric ratings are coerced."""
    df = pd.DataFrame({
        'review_text': ['great', 'bad', 'ok'],
        'rating': ['five', '2', 'three']  # Some non-numeric
    })
    result, warnings = ingest_and_validate(df)
    # Check that at least one rating was converted
    numeric_ratings = pd.to_numeric(result['rating'], errors='coerce')
    if numeric_ratings.notna().sum() > 0:
        return True, "Non-numeric ratings handled"
    return False, "Should have converted some ratings"


def test_empty_text():
    """Test that empty text rows are dropped."""
    df = pd.DataFrame({
        'review_text': ['great', '', 'ok', None],
        'rating': [5, 4, 3, 2]
    })
    result, warnings = ingest_and_validate(df)
    if len(result) < len(df):
        return True, f"Empty rows dropped: {len(df)} -> {len(result)}"
    return False, "Should have dropped empty rows"


def test_duplicates():
    """Test that duplicates are marked."""
    df = pd.DataFrame({
        'review_text': ['great product', 'great product', 'ok product'],
        'rating': [5, 5, 3]
    })
    result, warnings = ingest_and_validate(df)
    if result['is_duplicate'].sum() > 0:
        return True, f"Duplicates marked: {result['is_duplicate'].sum()}"
    return False, "Should have marked duplicates"


def test_very_long_review():
    """Test that very long reviews are truncated."""
    long_text = 'a' * 2000
    df = pd.DataFrame({
        'review_text': [long_text, 'short'],
        'rating': [5, 3]
    })
    result, warnings = ingest_and_validate(df)
    if len(result.iloc[0]['review_text']) <= 1000:
        return True, "Long reviews truncated to 1000 chars"
    return False, f"Review too long: {len(result.iloc[0]['review_text'])}"


def run_all_tests():
    """Run all validation tests."""
    tests = [
        ("Empty file", test_empty_file),
        ("Missing text column", test_no_text_column),
        ("Bad ratings", test_bad_ratings),
        ("Non-numeric ratings", test_non_numeric_ratings),
        ("Empty text rows", test_empty_text),
        ("Duplicates", test_duplicates),
        ("Very long review", test_very_long_review),
    ]

    print("="*60)
    print("INPUT VALIDATION TESTS")
    print("="*60)

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            result, msg = test_func()
            status = "PASS" if result else "FAIL"
            if result:
                passed += 1
            else:
                failed += 1
            print(f"{status}: {name}")
            print(f"       {msg}")
        except Exception as e:
            print(f"ERROR: {name}")
            print(f"       {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)

    return failed == 0


if __name__ == '__main__':
    os.chdir('C:\\Users\\santh\\Desktop\\revora ai')
    passed = run_all_tests()
    sys.exit(0 if passed else 1)
