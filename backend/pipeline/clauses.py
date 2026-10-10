"""Clause splitting."""
import re
from typing import List
from backend.schemas import ClauseRecord


def split_clauses(df) -> List[ClauseRecord]:
    """
    Split reviews into clauses at punctuation and contrast words.
    """
    clause_list = []
    clause_counter = 0

    for _, row in df.iterrows():
        review_id = row['review_id']
        text = row['review_text']

        if not isinstance(text, str) or len(text.strip()) == 0:
            continue

        # Split on punctuation and contrast words
        raw_clauses = split_on_punctuation_and_contrasts(text)

        for clause_text in raw_clauses:
            clause_text = clause_text.strip()
            if len(clause_text) > 0:
                clause_id = f"clause_{clause_counter}"
                clause = ClauseRecord(
                    review_id=review_id,
                    clause_id=clause_id,
                    clause_text=clause_text,
                    aspect=None,
                    score=0.0,
                    polarity='neu',
                    confidence=0.0,
                    score_source='unscored',
                    sarcasm_suspect=False,
                    rating_conflict=False,
                    safety_tier='none',
                    cluster_id=None
                )
                clause_list.append(clause)
                clause_counter += 1

    return clause_list


def split_on_punctuation_and_contrasts(text: str) -> List[str]:
    """
    Split text on punctuation (. ! ? ,) and contrast words (but, however, lekin, par, magar).
    """
    # Normalize contrasts
    contrast_pattern = r'\b(but|however|lekin|par|magar|although|though)\b'
    text = re.sub(contrast_pattern, r'. \1', text, flags=re.IGNORECASE)

    # Split on sentence-ending punctuation
    clauses = re.split(r'[.!?]+', text)

    # Split on commas for short text (if no sentence boundary)
    result = []
    for clause in clauses:
        if len(clause) > 100:  # Long clause, keep it
            result.append(clause)
        else:
            # Short clause, split on commas
            sub_clauses = re.split(r',', clause)
            result.extend(sub_clauses)

    return result
