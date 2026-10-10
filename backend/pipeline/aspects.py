"""Aspect tagging."""
import re
import yaml
from typing import List
from backend.schemas import ClauseRecord


ASPECT_SEEDS = None  # Loaded on first call


def load_aspect_seeds():
    """Load aspect seeds from config."""
    global ASPECT_SEEDS
    if ASPECT_SEEDS is not None:
        return ASPECT_SEEDS

    try:
        with open('backend/config/aspects.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            ASPECT_SEEDS = config.get('aspects', {})
    except FileNotFoundError:
        ASPECT_SEEDS = {}

    return ASPECT_SEEDS


def tag_aspects(clause_list: List[ClauseRecord], mode: str = 'lite') -> List[ClauseRecord]:
    """
    Tag each clause with an aspect (lite mode: keyword matching only).
    """
    seeds = load_aspect_seeds()

    # Build keyword -> aspect mappings
    keyword_to_aspect = {}
    for aspect_name, aspect_data in seeds.items():
        for lang_group in aspect_data.values():
            if isinstance(lang_group, list):
                for keyword in lang_group:
                    keyword_to_aspect[keyword.lower()] = aspect_name

    # Tag each clause
    for clause in clause_list:
        text = clause.clause_text.lower()
        words = set(re.findall(r'\b\w+\b', text))

        # Find matching aspect
        matched_aspect = None
        for word in words:
            if word in keyword_to_aspect:
                matched_aspect = keyword_to_aspect[word]
                break

        clause.aspect = matched_aspect if matched_aspect else 'other'

    return clause_list
