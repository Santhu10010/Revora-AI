"""Sentiment scoring."""
import re
import os
from typing import List, Optional
from backend.schemas import ClauseRecord
import yaml


HINGLISH_LEXICON = None
TRANSFORMER_MODEL = None  # Lazy-loaded for full mode


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


def load_transformer_model():
    """Lazy-load XLM-T transformer for full mode."""
    global TRANSFORMER_MODEL
    if TRANSFORMER_MODEL is not None:
        return TRANSFORMER_MODEL

    try:
        from transformers import pipeline
        TRANSFORMER_MODEL = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
            device=-1  # CPU
        )
        return TRANSFORMER_MODEL
    except Exception as e:
        print(f"Failed to load transformer: {e}")
        return None


def score_sentiment(clause_list: List[ClauseRecord], mode: str = 'lite') -> List[ClauseRecord]:
    """
    Score sentiment for each clause.
    Lite mode: lexicon + rating prior
    Full mode: blend transformer + lexicon + rating prior
    Also applies sarcasm and rating-conflict checks.
    """
    lexicon = load_hinglish_lexicon()
    transformer = None

    if mode == 'full':
        transformer = load_transformer_model()

    for clause in clause_list:
        text = clause.clause_text.lower()
        words = text.split()

        # Lexicon score
        lex_score = compute_lexicon_score(words, lexicon)

        # Transformer score (full mode only)
        transformer_score = 0.0
        if transformer:
            try:
                result = transformer(text[:512], truncation=True)
                label = result[0]['label']
                confidence = result[0]['score']

                if label == 'POS':
                    transformer_score = confidence
                elif label == 'NEG':
                    transformer_score = -confidence
            except Exception:
                transformer_score = 0.0

        # Blend scores
        if mode == 'full':
            clause.score = 0.5 * transformer_score + 0.35 * lex_score
            clause.score_source = 'blend'
        else:
            clause.score = lex_score
            clause.score_source = 'lexicon'

        clause.score = max(-1.0, min(1.0, clause.score))

        # Determine polarity
        if clause.score < -0.2:
            clause.polarity = 'neg'
        elif clause.score > 0.2:
            clause.polarity = 'pos'
        else:
            clause.polarity = 'neu'

        clause.confidence = min(0.9, abs(clause.score) + 0.3)

        # Sarcasm checks
        check_sarcasm(clause, words)

    return clause_list


def check_sarcasm(clause: ClauseRecord, words: list) -> None:
    """
    Apply sarcasm detection rules.
    Rule 1: positive phrase + failure event = sarcasm
    Rule 2: text polarity vs rating conflict (checked later with actual rating)
    """
    text = ' '.join(words)

    # Rule 1: positive words + failure events
    positive_words = {'great', 'amazing', 'awesome', 'excellent', 'perfect', 'fantastic',
                     'wonderful', 'love', 'thanks', 'thankyou', 'wow', 'waah', 'brilliant'}
    failure_words = {'broke', 'broken', 'stopped', 'stopped_working', 'died', 'dead',
                    'failed', 'fail', 'late', 'delayed', 'damaged', 'cracked', 'useless',
                    'waste', 'terrible', 'horrible', 'awful', 'worst', 'kharab', 'bekaar',
                    'ghatiya', 'bakwaas'}

    has_positive = any(word in text for word in positive_words)
    has_failure = any(word in text for word in failure_words)

    if has_positive and has_failure:
        clause.sarcasm_suspect = True


def compute_lexicon_score(words: list, lexicon: dict) -> float:
    """Compute sentiment score from lexicon with better context handling."""
    lex_score = 0.0
    has_negation = False
    intensifier_count = 0
    word_count = len([w for w in words if len(w) > 2])

    for i, word in enumerate(words):
        if word in lexicon['negation']:
            has_negation = True
        if word in lexicon['intensifier']:
            intensifier_count += 1
        if word in lexicon['positive']:
            lex_score += lexicon['positive'][word]
        elif word in lexicon['negative']:
            lex_score -= lexicon['negative'][word]

    # Apply negation only if negation found and score is non-zero
    if has_negation and lex_score != 0:
        lex_score *= -0.8  # Soften negation slightly to avoid over-flipping

    # Apply intensifiers
    if intensifier_count > 0:
        lex_score *= (1.0 + 0.15 * intensifier_count)

    # Normalize to -1 to 1
    if lex_score > 0:
        lex_score = min(1.0, lex_score / 4.0)  # More conservative scaling
    elif lex_score < 0:
        lex_score = max(-1.0, lex_score / 4.0)

    return lex_score
