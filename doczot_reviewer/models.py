"""Data models for the DocZot Expert Reviewer."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from doczot_analyzer.models import Endpoint, AnalysisReport


class JudgmentType(str, Enum):
    """Type of judgment made by the reviewer."""
    APPROVE = "approve"
    REJECT = "reject"
    ADJUST = "adjust"
    SKIP = "skip"


class EndpointJudgment(BaseModel):
    """User's judgment on a specific endpoint match."""
    endpoint_id: str  # Unique identifier (method + path)
    judgment_type: JudgmentType
    adjusted_confidence: Optional[float] = None  # If judgment_type == ADJUST
    notes: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class ReviewSession(BaseModel):
    """A review session for analyzing a repository."""
    session_id: str
    repo_path: str
    created_at: datetime = Field(default_factory=datetime.now)
    report: AnalysisReport
    judgments: List[EndpointJudgment] = Field(default_factory=list)
    
    @property
    def progress(self) -> Dict[str, int]:
        """Calculate review progress."""
        total = len(self.report.endpoints)
        reviewed = len(self.judgments)
        return {
            "total": total,
            "reviewed": reviewed,
            "pending": total - reviewed
        }
    
    def get_endpoint(self, endpoint_id: str) -> Optional[Endpoint]:
        """Get endpoint by ID."""
        for ep in self.report.endpoints:
            if f"{ep.method}_{ep.path}" == endpoint_id:
                return ep
        return None


class ReviewResult(BaseModel):
    """Aggregated results for export."""
    session_id: str
    repo_path: str
    total_endpoints: int
    judgments: List[EndpointJudgment]
    statistics: Dict[str, Any]  # Agreement rate, adjustments, etc.
    exported_at: datetime = Field(default_factory=datetime.now)
