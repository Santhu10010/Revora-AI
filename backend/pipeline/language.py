"""Language and script detection."""
import pandas as pd
import re
from typing import Tuple


def detect_language_and_script(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect language and script for each review.
    Lite mode: Unicode script ranges only.
    Full mode would add fastText detector.
    """
    df = df.copy()

    # Detect scripts first
    df[['script', 'is_romanized']] = df['review_text'].apply(
        lambda x: pd.Series(detect_script(x))
    )

    # Detect language (lite mode: script + function words)
    df[['lang', 'lang_confidence', 'lang_tier']] = df['review_text'].apply(
        lambda x: pd.Series(detect_language_lite(x, df.loc[df['review_text'] == x].iloc[0]['script']))
    )

    return df


def detect_script(text: str) -> Tuple[str, bool]:
    """
    Detect the primary script in the text.
    Returns (script, is_romanized)
    """
    if not isinstance(text, str):
        return 'other', False

    # Count characters in each script range
    scripts = {
        'devanagari': 0,
        'kannada': 0,
        'tamil': 0,
        'telugu': 0,
        'arabic': 0,
        'cjk': 0,
        'latin': 0,
    }

    for char in text:
        code = ord(char)
        # Devanagari: U+0900 to U+097F
        if 0x0900 <= code <= 0x097F:
            scripts['devanagari'] += 1
        # Kannada: U+0C80 to U+0CFF
        elif 0x0C80 <= code <= 0x0CFF:
            scripts['kannada'] += 1
        # Tamil: U+0B80 to U+0BFF
        elif 0x0B80 <= code <= 0x0BFF:
            scripts['tamil'] += 1
        # Telugu: U+0C00 to U+0C7F
        elif 0x0C00 <= code <= 0x0C7F:
            scripts['telugu'] += 1
        # Arabic: U+0600 to U+06FF
        elif 0x0600 <= code <= 0x06FF:
            scripts['arabic'] += 1
        # CJK: U+4E00 to U+9FFF, U+3040 to U+309F (Japanese), U+AC00 to U+D7AF (Korean)
        elif (0x4E00 <= code <= 0x9FFF) or (0x3040 <= code <= 0x309F) or (0xAC00 <= code <= 0xD7AF):
            scripts['cjk'] += 1
        # Latin: U+0041 to U+005A, U+0061 to U+007A
        elif (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A):
            scripts['latin'] += 1

    # Determine primary script
    total_non_latin = sum(v for k, v in scripts.items() if k != 'latin')
    if total_non_latin > scripts['latin']:
        # Mixed or native script
        max_script = max((k for k in scripts if k != 'latin'), key=lambda k: scripts[k])
        is_romanized = False
        return max_script, is_romanized
    else:
        # Primarily Latin (romanized)
        return 'latin', True


def detect_language_lite(text: str, script: str) -> Tuple[str, float, int]:
    """
    Lite mode language detection: script + function words.
    Returns (lang, confidence, tier)
    """
    if not isinstance(text, str):
        return 'und', 0.0, 4

    text_lower = text.lower()

    # Function word patterns for romanized Indian languages
    hinglish_words = {'hai', 'hain', 'h', 'nahi', 'nhi', 'ka', 'ki', 'ke', 'aur', 'par', 'lekin'}
    kannada_words = {'anna', 'anu', 'illa', 'hege', 'kano', 'guru'}  # Simplified
    tamil_words = {'um', 'ah', 'la', 'le', 'uh', 'ku', 'va'}  # Simplified
    telugu_words = {'dhi', 'dhaa', 'ledu', 'undi', 'kanu', 'ki'}  # Simplified

    # Count matches
    words = text_lower.split()
    hinglish_score = sum(1 for w in words if w in hinglish_words)
    kannada_score = sum(1 for w in words if w in kannada_words)
    tamil_score = sum(1 for w in words if w in tamil_words)
    telugu_score = sum(1 for w in words if w in telugu_words)

    # If native script, map to language
    if script in ('devanagari',):
        return 'hi', 0.8, 1
    elif script == 'kannada':
        return 'kn', 0.8, 3
    elif script == 'tamil':
        return 'ta', 0.8, 3
    elif script == 'telugu':
        return 'te', 0.8, 3
    elif script == 'arabic':
        return 'ar', 0.7, 4
    elif script == 'cjk':
        return 'zh', 0.7, 4

    # For Latin script, check function words
    max_score = max(hinglish_score, kannada_score, tamil_score, telugu_score)

    if hinglish_score > 0 and hinglish_score == max_score:
        confidence = min(0.9, hinglish_score / max(1, len(words)) + 0.5)
        return 'hinglish', confidence, 1
    elif kannada_score > 0 and kannada_score == max_score:
        confidence = min(0.9, kannada_score / max(1, len(words)) + 0.4)
        return 'kanglish', confidence, 2
    elif tamil_score > 0 and tamil_score == max_score:
        confidence = min(0.9, tamil_score / max(1, len(words)) + 0.4)
        return 'tanglish', confidence, 2
    elif telugu_score > 0 and telugu_score == max_score:
        confidence = min(0.9, telugu_score / max(1, len(words)) + 0.4)
        return 'tenglish', confidence, 2
    else:
        # Default to English
        return 'en', 0.7, 1
