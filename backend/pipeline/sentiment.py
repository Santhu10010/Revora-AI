"""Sentiment scoring."""
import re
from typing import List
from backend.schemas import ClauseRecord
import yaml


HINGLISH_LEXICON = None


def load_hinglish_lexicon():
    """Load Hinglish sentiment lexicon."""
    global HINGLISH_LEXICON
    if HINGLISH_LEXICON is not None:
        return HINGLISH_LEXICON

    HINGLISH_LEXICON = {
        'positive': {},
        'negative': {},
        'negation': set(),
        'intensifier': set(),
    }

    try:
        with open('backend/config/hinglish_lexicon.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split('\t')
                if len(parts) < 2:
                    continue

                word, polarity = parts[0], parts[1]

                if polarity == 'pos':
                    intensity = float(parts[2]) if len(parts) > 2 else 1.0
                    HINGLISH_LEXICON['positive'][word] = intensity
                elif polarity == 'neg':
                    intensity = float(parts[2]) if len(parts) > 2 else 1.0
                    HINGLISH_LEXICON['negative'][word] = intensity
                elif polarity == 'negation':
                    HINGLISH_LEXICON['negation'].add(word)
                elif polarity == 'intensifier':
                    HINGLISH_LEXICON['intensifier'].add(word)
    except FileNotFoundError:
        pass

    return HINGLISH_LEXICON


def score_sentiment(clause_list: List[ClauseRecord], mode: str = 'lite') -> List[ClauseRecord]:
    """
    Score sentiment for each clause (lite mode: lexicon + rating prior).
    """
    lexicon = load_hinglish_lexicon()

    for clause in clause_list:
        text = clause.clause_text.lower()
        words = text.split()

        # Lexicon score
        lex_score = 0.0
        has_negation = False
        intensifier_count = 0

        for i, word in enumerate(words):
            if word in lexicon['negation']:
                has_negation = True
            if word in lexicon['intensifier']:
                intensifier_count += 1
            if word in lexicon['positive']:
                lex_score += lexicon['positive'][word]
            elif word in lexicon['negative']:
                lex_score -= lexicon['negative'][word]

        # Apply negation (flip score)
        if has_negation:
            lex_score *= -1

        # Apply intensifiers
        if intensifier_count > 0:
            lex_score *= (1.0 + 0.2 * intensifier_count)

        # Normalize to -1 to 1
        if lex_score > 0:
            lex_score = min(1.0, lex_score / 3.0)
        elif lex_score < 0:
            lex_score = max(-1.0, lex_score / 3.0)

        clause.score = lex_score
        clause.score_source = 'lexicon'

        # Determine polarity
        if clause.score < -0.25:
            clause.polarity = 'neg'
        elif clause.score > 0.25:
            clause.polarity = 'pos'
        else:
            clause.polarity = 'neu'

        clause.confidence = min(0.9, abs(clause.score) + 0.3)

    return clause_list
