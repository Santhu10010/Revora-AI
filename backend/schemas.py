"""Pydantic schemas for Revora AI data contract."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ReviewRecord(BaseModel):
    """A single review record from the data contract."""
    review_id: str
    text: str
    rating: Optional[float] = None
    date: Optional[str] = None
    version: Optional[str] = None
    lang: str = Field(default="und", description="ISO code or hinglish, kanglish, tanglish, tenglish, mixed, und")
    script: str = Field(default="other", description="latin, devanagari, kannada, tamil, telugu, arabic, cjk, other, mixed")
    is_romanized: bool = False
    lang_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    lang_tier: int = Field(default=4, ge=1, le=4)
    translated_text: Optional[str] = None
    is_duplicate: bool = False
    rating_source: str = Field(default="given", description="given or pseudo")


class ClauseRecord(BaseModel):
    """A single clause (aspect-sentiment pair) from a review."""
    review_id: str
    clause_id: str
    clause_text: str
    aspect: Optional[str] = None
    score: float = Field(ge=-1.0, le=1.0)
    polarity: str = Field(description="neg, neu, pos")
    confidence: float = Field(ge=0.0, le=1.0)
    score_source: str = Field(description="lexicon, blend, rating_prior, translated, unscored")
    sarcasm_suspect: bool = False
    rating_conflict: bool = False
    safety_tier: str = Field(default="none", description="none, medium, high, critical")
    cluster_id: Optional[str] = None


class ClusterRecord(BaseModel):
    """A cluster of similar clauses."""
    cluster_id: str
    aspect: Optional[str] = None
    polarity: str = Field(description="neg, neu, pos")
    label: str = Field(description="Human-readable cluster label")
    example_clause_id: str
    size: int = Field(ge=1)


class InsightRecord(BaseModel):
    """An insight: an aspect-polarity pair with impact metrics."""
    aspect: Optional[str] = None
    polarity: str = Field(description="neg, neu, pos")
    mentions: int = Field(ge=0)
    pct_negative: float = Field(ge=0.0, le=1.0)
    beta: Optional[float] = None  # rating damage coefficient
    ci_low: Optional[float] = None  # confidence interval low
    ci_high: Optional[float] = None  # confidence interval high
    damage: Optional[float] = None  # mentions * |beta|
    priority_rank: int = Field(ge=0)
    confidence_label: str = Field(default="ok", description="ok or low")
    single_cause_unhappy: int = Field(default=0, ge=0)


class AnalysisMetadata(BaseModel):
    """Metadata about an analysis run."""
    mode: str = Field(description="lite or full")
    total_reviews: int = Field(ge=0)
    total_clauses: int = Field(ge=0)
    total_clusters: int = Field(ge=0)
    reviews_with_rating: int = Field(ge=0)
    avg_rating: Optional[float] = None
    pct_negative: float = Field(ge=0.0, le=1.0)
    warnings: List[str] = Field(default_factory=list)
    processing_ms: int = Field(ge=0)
    languages_detected: Dict[str, int] = Field(default_factory=dict)
    safety_cases: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AnalysisResults(BaseModel):
    """Complete analysis results: the four tables plus metadata."""
    reviews: List[ReviewRecord]
    clauses: List[ClauseRecord]
    clusters: List[ClusterRecord]
    insights: List[InsightRecord]
    meta: AnalysisMetadata
