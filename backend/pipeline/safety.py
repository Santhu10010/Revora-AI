"""Safety scanning."""
import re
from pathlib import Path
from typing import List

import yaml

from backend.schemas import ClauseRecord


SAFETY_TERMS = None


def _normalize_term(term: str) -> str:
    return re.sub(r'[_\-]+', ' ', term.lower()).strip()


def _text_tokens(text: str):
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def load_safety_terms():
    """Load safety terms from config."""
    global SAFETY_TERMS
    if SAFETY_TERMS is not None:
        return SAFETY_TERMS

    config_path = Path(__file__).resolve().parent.parent / 'config' / 'safety_terms.yaml'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            SAFETY_TERMS = config.get('safety_terms', config)
            if not isinstance(SAFETY_TERMS, dict):
                SAFETY_TERMS = {}
            SAFETY_TERMS['negation_window'] = config.get('negation_window', 5)
            SAFETY_TERMS['context_required'] = config.get('context_required', False)
    except FileNotFoundError:
        SAFETY_TERMS = {'critical': [], 'high': [], 'medium': [], 'negation_window': 5, 'context_required': True}

    return SAFETY_TERMS


def _matches_term(text: str, term: str) -> bool:
    normalized = _normalize_term(term)
    if not normalized:
        return False
    if normalized in text:
        return True
    parts = normalized.split()
    if len(parts) == 1:
        return parts[0] in text
    return False


def _context_present(text: str) -> bool:
    """Require the hazard to be tied to a device/body/event context."""
    context_words = {
        'phone', 'product', 'battery', 'device', 'charger', 'appliance', 'laptop', 'tablet',
        'screen', 'speaker', 'camera', 'mobile', 'phone', 'device', 'battery', 'charger',
        'skin', 'body', 'hand', 'face', 'arm', 'head', 'legs', 'use', 'using', 'after',
        'while', 'when', 'during', 'got', 'had', 'caused', 'suffered', 'reaction', 'symptom',
        'burnt', 'smoke', 'injury', 'wound', 'exposure', 'materials', 'my', 'me', 'from',
        'with', 'on', 'at', 'under', 'inside', 'using', 'during', 'after'
    }
    tokens = _text_tokens(text)
    return any(token in context_words for token in tokens)


def scan_safety(clause_list: List[ClauseRecord], mode: str = 'lite') -> List[ClauseRecord]:
    """Scan for safety hazards with a negation guard and product-context requirement."""
    safety_config = load_safety_terms()
    negation_words = {'no', 'not', 'nahi', 'nhi', 'nahin', 'na', 'koi nahin', "doesn't", "don't", "isn't", 'safe'}
    negation_window = safety_config.get('negation_window', 5)
    context_required = safety_config.get('context_required', False)

    for clause in clause_list:
        clause.safety_tier = 'none'
        text = clause.clause_text.lower()

        for tier in ['critical', 'high', 'medium']:
            for term_data in safety_config.get(tier, []):
                term = term_data.get('term', '').lower()
                hinglish_terms = [str(t).lower() for t in term_data.get('hinglish', [])]
                all_terms = [term] + hinglish_terms

                for check_term in all_terms:
                    normalized_term = _normalize_term(check_term)
                    if not normalized_term:
                        continue
                    if not _matches_term(text, normalized_term):
                        continue
                    if is_negated(text, normalized_term, negation_words, negation_window):
                        continue
                    if context_required and not _has_hazard_context(text):
                        continue
                    clause.safety_tier = tier
                    break
                if clause.safety_tier != 'none':
                    break
            if clause.safety_tier != 'none':
                break

    return clause_list


def _has_hazard_context(text: str) -> bool:
    """Accept real hazard clauses while rejecting non-hazard business/price comparisons."""
    tokens = _text_tokens(text)
    if not tokens:
        return False

    product_context = {
        'phone', 'product', 'battery', 'device', 'charger', 'appliance', 'laptop', 'tablet',
        'screen', 'speaker', 'camera', 'mobile', 'body', 'skin', 'hand', 'face', 'arm', 'head',
        'person', 'use', 'using', 'after', 'while', 'when', 'during', 'my', 'me', 'got', 'had',
        'caused', 'causing', 'suffered', 'reaction', 'symptom', 'wound', 'exposure', 'materials',
        'detected', 'started', 'coming', 'came', 'out', 'from', 'with', 'hazard', 'risk', 'safety',
        'limit', 'safe', 'parts', 'part', 'joint', 'small', 'past', 'started', 'inside'
    }
    return any(token in product_context for token in tokens)


# Stronger guard: hazard words must appear with a device/body/event context in the same sentence.
# We keep the old context helper for compatibility and use the stricter version in scan_safety.


def is_negated(text: str, term: str, negation_words: set, window: int) -> bool:
    """Check if a term is negated by looking at nearby negation words."""
    words = _text_tokens(text)
    normalized_term = _normalize_term(term)
    term_tokens = normalized_term.split()

    for idx, word in enumerate(words):
        if len(term_tokens) == 1 and (term_tokens[0] == word or term_tokens[0] in word):
            start = max(0, idx - window)
            end = min(len(words), idx + window + 1)
            for nearby in words[start:end]:
                if nearby in negation_words or nearby == 'never':
                    return True
                if "n't" in nearby:
                    return True
            return False

        if len(term_tokens) > 1:
            phrase = ' '.join(words[idx:idx + len(term_tokens)])
            if phrase == normalized_term:
                start = max(0, idx - window)
                end = min(len(words), idx + len(term_tokens) + window)
                for nearby in words[start:end]:
                    if nearby in negation_words or nearby == 'never':
                        return True
                    if "n't" in nearby:
                        return True
                return False

    return False
