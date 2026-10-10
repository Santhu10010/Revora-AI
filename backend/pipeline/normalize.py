"""Text normalization."""
import pandas as pd
import re


def normalize_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize review text.
    - Lowercase
    - Collapse repeated letters
    - Redact emails and phone numbers
    """
    df = df.copy()
    df['review_text'] = df['review_text'].apply(normalize_text)
    return df


def normalize_text(text: str) -> str:
    """Normalize a single review text."""
    if not isinstance(text, str):
        return text

    # Lowercase
    text = text.lower()

    # Collapse repeated letters (bahuuut -> bahut, greeeaaat -> great)
    text = re.sub(r'([a-z])\1{2,}', r'\1', text)

    # Redact phone numbers (simple pattern: 10 digits)
    text = re.sub(r'\b\d{10}\b', '[PHONE]', text)
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)

    # Redact emails
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)

    # Strip extra whitespace
    text = ' '.join(text.split())

    return text
