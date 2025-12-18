"""FastAPI backend for DocZot Expert Reviewer."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List
from pydantic import BaseModel
import json
import uuid
from pathlib import Path
from datetime import datetime

from doczot_reviewer.models import (
    ReviewSession,
    EndpointJudgment,
    ReviewResult,
    JudgmentType
)
from doczot_analyzer.models import AnalysisReport

app = FastAPI(title="DocZot Expert Reviewer")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (replace with DB for production)
sessions: Dict[str, ReviewSession] = {}


class CreateSessionRequest(BaseModel):
    repo_path: str
    results_file: str


@app.post("/sessions", response_model=ReviewSession)
async def create_session(request: CreateSessionRequest):
    """Create a new review session from analysis results."""
    # Load analysis results
    results_path = Path(request.results_file)
    if not results_path.exists():
        raise HTTPException(status_code=404, detail="Results file not found")
    
    with open(results_path) as f:
        data = json.load(f)
    
    # Parse report
    report = AnalysisReport(**data["report"])
    
    # Create session
    session = ReviewSession(
        session_id=str(uuid.uuid4()),
        repo_path=request.repo_path,
        report=report
    )
    
    sessions[session.session_id] = session
    return session


@app.get("/sessions/{session_id}", response_model=ReviewSession)
async def get_session(session_id: str):
    """Get review session by ID."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]


@app.get("/sessions/{session_id}/endpoints/{endpoint_id}")
async def get_endpoint(session_id: str, endpoint_id: str):
    """Get specific endpoint details with match information."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    endpoint = session.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    return {
        "endpoint": endpoint,
        "existing_judgment": next(
            (j for j in session.judgments if j.endpoint_id == endpoint_id),
            None
        )
    }


@app.post("/sessions/{session_id}/judgments")
async def submit_judgment(session_id: str, judgment: EndpointJudgment):
    """Submit a judgment for an endpoint."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Remove existing judgment if present
    session.judgments = [
        j for j in session.judgments if j.endpoint_id != judgment.endpoint_id
    ]
    
    # Add new judgment
    session.judgments.append(judgment)
    
    return {"status": "success", "progress": session.progress}


@app.get("/sessions/{session_id}/export", response_model=ReviewResult)
async def export_results(session_id: str):
    """Export review results with statistics."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Calculate statistics
    judgments_by_type = {}
    for j in session.judgments:
        judgments_by_type[j.judgment_type] = judgments_by_type.get(j.judgment_type, 0) + 1
    
    approved = judgments_by_type.get(JudgmentType.APPROVE, 0)
    total_reviewed = len(session.judgments)
    
    statistics = {
        "by_type": judgments_by_type,
        "approval_rate": approved / total_reviewed if total_reviewed > 0 else 0,
        "review_completion": total_reviewed / len(session.report.endpoints)
    }
    
    return ReviewResult(
        session_id=session.session_id,
        repo_path=session.repo_path,
        total_endpoints=len(session.report.endpoints),
        judgments=session.judgments,
        statistics=statistics
    )


@app.get("/")
async def root():
    """Health check."""
    return {"status": "ok", "app": "DocZot Expert Reviewer"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
