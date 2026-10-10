"""Safety scanning."""
import re
from typing import List
from backend.schemas import ClauseRecord
import yaml


SAFETY_TERMS = None


def load_safety_terms():
    """Load safety terms from config."""
    global SAFETY_TERMS
    if SAFETY_TERMS is not None:
        return SAFETY_TERMS

    try:
        with open('backend/config/safety_terms.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            # Get the safety_terms section
            SAFETY_TERMS = config.get('safety_terms', config)
            if not isinstance(SAFETY_TERMS, dict):
                SAFETY_TERMS = {}
    except FileNotFoundError:
        SAFETY_TERMS = {'critical': [], 'high': [], 'medium': []}

    return SAFETY_TERMS


def scan_safety(clause_list: List[ClauseRecord], mode: str = 'lite') -> List[ClauseRecord]:
    """
    Scan for safety hazards with negation and context guards.
    """
    safety_config = load_safety_terms()
    negation_words = {'no', 'not', 'nahi', 'nhi', 'nahin', 'na', 'koi nahin'}
    negation_window = safety_config.get('negation_window', 5)

    for clause in clause_list:
        text = clause.clause_text.lower()
        words = text.split()

        # Check each tier
        for tier in ['critical', 'high', 'medium']:
            tier_matched = False
            for term_data in safety_config.get(tier, []):
                term = term_data.get('term', '').lower()
                hinglish_terms = [t.lower() for t in term_data.get('hinglish', [])]
                all_terms = [term] + hinglish_terms

                # Check if any term appears in the text
                for check_term in all_terms:
                    if check_term in text or any(check_term in w for w in words):
                        # Negation guard: check if term is negated
                        if is_negated(text, check_term, negation_words, negation_window):
                            continue

                        # Context guard: check if term co-occurs with product/body context
                        context_words = {'product', 'device', 'phone', 'earbuds', 'battery',
                                       'charger', 'skin', 'hand', 'body', 'burn', 'broke',
                                       'stopped', 'late', 'stopped working'}
                        if any(ctx in text for ctx in context_words):
                            clause.safety_tier = tier
                            tier_matched = True
                            break

                if tier_matched:
                    break

    return clause_list


def is_negated(text: str, term: str, negation_words: set, window: int) -> bool:
    """
    Check if a term is negated by looking at nearby negation words.
    """
    words = text.split()

    # Find position of term
    term_pos = -1
    for i, word in enumerate(words):
        if term in word:
            term_pos = i
            break

    if term_pos == -1:
        return False

    # Check window around term for negation
    start = max(0, term_pos - window)
    end = min(len(words), term_pos + window + 1)

    for i in range(start, end):
        if i != term_pos and words[i] in negation_words:
            return True

    return False
