from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Claim(BaseModel):
    id: int
    claim_text: str
    language: Optional[str] = None
    verdict: Optional[str] = None
    confidence: Optional[int] = None
    explanation: Optional[str] = None
    sources: List[str] = []
    virality_score: Optional[int] = None
    timestamp: str
    disputed: bool = False


class DashboardStats(BaseModel):
    total_messages: int
    verdict_counts: Dict[str, int]
    language_distribution: Dict[str, int]
    top_viral_claims: List[Dict[str, Any]]
    false_vs_true: Dict[str, int]
    trending_categories: Dict[str, int]


class UpdateClaimRequest(BaseModel):
    id: int
    verdict: Optional[str] = None
    confidence: Optional[int] = None
    explanation: Optional[str] = None
    sources: Optional[List[str]] = None
    disputed: Optional[bool] = None


class ProcessedClaimResponse(BaseModel):
    claim: str
    language: Optional[str]
    verdict: str
    confidence: int
    explanation: str
    sources: List[str]
    virality_score: int
    virality_reasoning: str
    counter_message: str
    from_cache: bool = False
    claim_id: Optional[int] = None

