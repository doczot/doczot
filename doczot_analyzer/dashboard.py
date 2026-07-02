"""DocZot Interactive Dashboard - FastAPI server with embedded HTML frontend.

Serves analysis results and handles user interactions via REST API.
The HTML dashboard is embedded as a string template for zero-dependency deployment.

Usage:
    from doczot_analyzer.dashboard import create_app
    app = create_app(db_path=".doczot/manifests.db")
    uvicorn.run(app, host="127.0.0.1", port=8456)
"""
from __future__ import annotations

import json
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from doczot_analyzer.storage import ManifestStore


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class AnalyzeRequest(BaseModel):
    repo_path: str
    product_name: Optional[str] = None


class JudgmentRequest(BaseModel):
    node_id: str
    topic_id: str
    judgment: str  # "accept", "reject", "unsure"
    notes: Optional[str] = None
    evidence_index: Optional[int] = None


class CustomTopicRequest(BaseModel):
    name: str
    topic_type: str = "task"
    description: Optional[str] = None
    covers: list[str] = []
    parent_id: Optional[str] = None
    priority: int = 0


class TopicUpdateRequest(BaseModel):
    name: Optional[str] = None
    topic_type: Optional[str] = None
    description: Optional[str] = None
    covers: Optional[list[str]] = None
    parent_id: Optional[str] = None
    priority: Optional[int] = None


# =============================================================================
# APP FACTORY
# =============================================================================

# Track running analyses
_running_analyses: dict[str, str] = {}  # session_id -> status


def create_app(db_path: str = ".doczot/manifests.db") -> FastAPI:
    """Create the FastAPI dashboard application.

    Args:
        db_path: Path to SQLite database

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(title="DocZot Dashboard", version="3.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    store = ManifestStore(db_path)

    # =========================================================================
    # DASHBOARD HTML
    # =========================================================================

    @app.get("/", response_class=HTMLResponse)
    async def serve_dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    # =========================================================================
    # ANALYSIS
    # =========================================================================

    @app.post("/api/analyze")
    async def run_analysis(req: AnalyzeRequest, background_tasks: BackgroundTasks):
        """Run analysis on a repo path. Returns session_id immediately."""
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        _running_analyses[session_id] = "running"

        background_tasks.add_task(
            _run_analysis_background, store, session_id, req.repo_path, req.product_name
        )

        return {"session_id": session_id, "status": "running"}

    @app.get("/api/analyze/{session_id}/status")
    async def analysis_status(session_id: str):
        """Check analysis status."""
        status = _running_analyses.get(session_id)
        if status:
            return {"session_id": session_id, "status": status}
        # Check if session exists in DB (completed)
        session = store.load_session(session_id)
        if session:
            return {"session_id": session_id, "status": "complete"}
        raise HTTPException(status_code=404, detail="Session not found")

    # =========================================================================
    # SESSIONS
    # =========================================================================

    @app.get("/api/sessions")
    async def list_sessions(product_name: Optional[str] = None):
        return store.list_sessions(product_name)

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str):
        session = store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        # Parse JSON fields
        result = dict(session)
        for field in ("itm_json", "atm_json", "drift_json", "doc_graph_json"):
            if result.get(field):
                result[field] = json.loads(result[field])
        return result

    # =========================================================================
    # SYSTEM GRAPH
    # =========================================================================

    @app.get("/api/sessions/{session_id}/graph")
    async def get_graph(session_id: str):
        session = store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        scan_id = session.get("graph_scan_id")
        if not scan_id:
            return {"nodes": [], "edges": []}
        graph = store.load_system_graph(
            session["product_name"], scan_id=scan_id
        )
        if not graph:
            return {"nodes": [], "edges": []}
        return graph.model_dump()

    # =========================================================================
    # COVERAGE CHECKLIST (ITM)
    # =========================================================================

    @app.get("/api/sessions/{session_id}/checklist")
    async def get_checklist(session_id: str):
        session = store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        itm = json.loads(session["itm_json"]) if session.get("itm_json") else {}
        # Merge in custom topics
        custom = store.load_custom_topics(session_id)
        return {"checklist": itm, "custom_topics": custom}

    @app.post("/api/sessions/{session_id}/checklist/topics")
    async def add_custom_topic(session_id: str, req: CustomTopicRequest):
        session = store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        topic_id = f"custom_{uuid.uuid4().hex[:8]}"
        topic_data = {
            "id": topic_id,
            "name": req.name,
            "topic_type": req.topic_type,
            "description": req.description,
            "covers": req.covers,
            "parent_id": req.parent_id,
            "priority": req.priority,
        }
        store.save_custom_topic(session_id, topic_data)
        return {"id": topic_id, "status": "created"}

    @app.put("/api/sessions/{session_id}/checklist/topics/{topic_id}")
    async def update_topic(session_id: str, topic_id: str, req: TopicUpdateRequest):
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        ok = store.update_custom_topic(topic_id, updates)
        if not ok:
            raise HTTPException(status_code=404, detail="Topic not found")
        return {"status": "updated"}

    @app.delete("/api/sessions/{session_id}/checklist/topics/{topic_id}")
    async def delete_topic(session_id: str, topic_id: str):
        ok = store.delete_custom_topic(topic_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Topic not found")
        return {"status": "deleted"}

    # =========================================================================
    # CONTENT INVENTORY (ATM)
    # =========================================================================

    @app.get("/api/sessions/{session_id}/inventory")
    async def get_inventory(session_id: str):
        session = store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        atm = json.loads(session["atm_json"]) if session.get("atm_json") else {}
        return atm

    # =========================================================================
    # JUDGMENTS
    # =========================================================================

    @app.get("/api/sessions/{session_id}/judgments")
    async def get_judgments(session_id: str):
        return store.load_judgments(session_id)

    @app.put("/api/sessions/{session_id}/judgments")
    async def save_judgment(session_id: str, req: JudgmentRequest):
        session = store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if req.judgment not in ("accept", "reject", "unsure"):
            raise HTTPException(status_code=400, detail="Invalid judgment")
        store.save_judgment(
            session_id=session_id,
            node_id=req.node_id,
            topic_id=req.topic_id,
            judgment=req.judgment,
            notes=req.notes,
            evidence_index=req.evidence_index,
        )
        return {"status": "saved"}

    @app.get("/api/sessions/{session_id}/judgments/progress")
    async def judgment_progress(session_id: str):
        session = store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        judgments = store.load_judgments(session_id)
        atm = json.loads(session["atm_json"]) if session.get("atm_json") else {}
        total_evidence = 0
        if atm and "topics" in atm:
            for topic in atm["topics"]:
                total_evidence += len(topic.get("match_evidence", []))
        judged = len(judgments)
        accepted = sum(1 for j in judgments if j["judgment"] == "accept")
        rejected = sum(1 for j in judgments if j["judgment"] == "reject")
        unsure = sum(1 for j in judgments if j["judgment"] == "unsure")
        return {
            "total_evidence": total_evidence,
            "judged": judged,
            "accepted": accepted,
            "rejected": rejected,
            "unsure": unsure,
            "progress": round(judged / total_evidence * 100, 1) if total_evidence else 0,
        }

    # =========================================================================
    # DRIFT & REPORTS
    # =========================================================================

    @app.get("/api/sessions/{session_id}/drift")
    async def get_drift(session_id: str):
        session = store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        drift = json.loads(session["drift_json"]) if session.get("drift_json") else {}
        return drift

    @app.get("/api/sessions/{session_id}/reports/coverage")
    async def coverage_report(session_id: str):
        session = store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        from doczot_analyzer.reports import generate_coverage_report
        return {"markdown": generate_coverage_report(session)}

    @app.get("/api/sessions/{session_id}/reports/missing")
    async def missing_report(session_id: str):
        session = store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        from doczot_analyzer.reports import generate_missing_docs_report
        return {"markdown": generate_missing_docs_report(session)}

    @app.get("/api/sessions/{session_id}/reports/sprint")
    async def sprint_report(session_id: str):
        session = store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        from doczot_analyzer.reports import generate_sprint_plan
        return {"markdown": generate_sprint_plan(session)}

    return app


# =============================================================================
# BACKGROUND ANALYSIS
# =============================================================================

def _run_analysis_background(
    store: ManifestStore,
    session_id: str,
    repo_path: str,
    product_name: Optional[str],
) -> None:
    """Run full analysis in background thread and save results."""
    try:
        from doczot_analyzer.analyzer_v2 import analyze_repository, save_analysis_session

        graph, itm, atm, drift = analyze_repository(repo_path, product_name)
        save_analysis_session(
            store, repo_path, graph, itm, atm, drift, session_id=session_id
        )

        _running_analyses[session_id] = "complete"
    except Exception as e:
        _running_analyses[session_id] = f"error: {e}"


# =============================================================================
# DASHBOARD HTML TEMPLATE
# =============================================================================

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DocZot Dashboard</title>
<style>
:root {
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --bg-tertiary: #334155;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent-blue: #3b82f6;
    --accent-purple: #a855f7;
    --accent-yellow: #eab308;
    --accent-red: #ef4444;
    --accent-green: #22c55e;
    --accent-cyan: #06b6d4;
    --border: #334155;
    --shadow: rgba(0,0,0,0.3);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    background: var(--bg-primary);
    color: var(--text-primary);
    height: 100vh;
    overflow: hidden;
}
.app {
    display: grid;
    grid-template-rows: auto 1fr auto;
    height: 100vh;
}
/* Header */
.header {
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    padding: 12px 20px;
    display: flex;
    align-items: center;
    gap: 16px;
}
.header h1 { font-size: 18px; font-weight: 600; }
.header .product-name { color: var(--accent-blue); font-size: 14px; }
.header .actions { margin-left: auto; display: flex; gap: 8px; }
.btn {
    padding: 6px 14px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-tertiary);
    color: var(--text-primary);
    cursor: pointer;
    font-size: 13px;
    transition: background 0.15s;
}
.btn:hover { background: var(--accent-blue); border-color: var(--accent-blue); }
.btn-primary { background: var(--accent-blue); border-color: var(--accent-blue); }
.btn-sm { padding: 3px 8px; font-size: 12px; }
.btn-accept { background: var(--accent-green); border-color: var(--accent-green); }
.btn-reject { background: var(--accent-red); border-color: var(--accent-red); }
/* Main layout */
.main {
    display: grid;
    grid-template-columns: 180px 1fr;
    overflow: hidden;
}
/* Nav */
.nav {
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    padding: 12px 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.nav-item {
    padding: 10px 16px;
    cursor: pointer;
    font-size: 13px;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.15s;
    border-left: 3px solid transparent;
}
.nav-item:hover { background: var(--bg-tertiary); color: var(--text-primary); }
.nav-item.active {
    background: var(--bg-tertiary);
    color: var(--accent-blue);
    border-left-color: var(--accent-blue);
}
.nav-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-muted);
}
.nav-item.active .nav-dot { background: var(--accent-blue); }
/* Content */
.content {
    overflow-y: auto;
    padding: 20px;
}
.content h2 { font-size: 20px; margin-bottom: 16px; }
.content h3 { font-size: 16px; margin-bottom: 12px; color: var(--text-secondary); }
/* Cards */
.card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
}
.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}
.card-title { font-weight: 600; font-size: 14px; }
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}
.badge-verb { background: rgba(59,130,246,0.2); color: var(--accent-blue); }
.badge-noun { background: rgba(168,85,247,0.2); color: var(--accent-purple); }
.badge-concept { background: rgba(234,179,8,0.2); color: var(--accent-yellow); }
.badge-constraint { background: rgba(239,68,68,0.2); color: var(--accent-red); }
.badge-complete { background: rgba(34,197,94,0.2); color: var(--accent-green); }
.badge-partial { background: rgba(234,179,8,0.2); color: var(--accent-yellow); }
.badge-missing { background: rgba(239,68,68,0.2); color: var(--accent-red); }
.badge-reference { background: rgba(6,182,212,0.2); color: var(--accent-cyan); }
.badge-task { background: rgba(168,85,247,0.2); color: var(--accent-purple); }
/* Evidence */
.evidence-card {
    background: var(--bg-tertiary);
    border-radius: 6px;
    padding: 12px;
    margin: 8px 0;
    border-left: 3px solid var(--text-muted);
}
.evidence-card.direct { border-left-color: var(--accent-green); }
.evidence-card.semantic { border-left-color: var(--accent-blue); }
.evidence-snippet {
    font-size: 12px;
    color: var(--text-secondary);
    margin: 4px 0;
    font-family: monospace;
    white-space: pre-wrap;
    max-height: 80px;
    overflow: hidden;
}
.evidence-actions { display: flex; gap: 6px; margin-top: 8px; }
/* Stats */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
}
.stat-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    text-align: center;
}
.stat-value { font-size: 28px; font-weight: 700; }
.stat-label { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
/* Table */
.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}
.data-table th {
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    color: var(--text-secondary);
    font-weight: 600;
}
.data-table td {
    padding: 8px 12px;
    border-bottom: 1px solid rgba(51,65,85,0.5);
}
.data-table tr:hover td { background: rgba(59,130,246,0.05); }
/* Status bar */
.status-bar {
    background: var(--bg-secondary);
    border-top: 1px solid var(--border);
    padding: 8px 20px;
    font-size: 12px;
    color: var(--text-secondary);
    display: flex;
    gap: 20px;
}
/* Graph view */
.graph-container {
    width: 100%;
    height: calc(100vh - 200px);
    position: relative;
}
.graph-container svg { width: 100%; height: 100%; }
/* Modal */
.modal-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
}
.modal {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    width: 480px;
    max-width: 90vw;
}
.modal h3 { margin-bottom: 16px; }
.modal input, .modal textarea, .modal select {
    width: 100%;
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-tertiary);
    color: var(--text-primary);
    font-size: 13px;
    margin-bottom: 12px;
}
.modal textarea { height: 80px; resize: vertical; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
/* Analyze form */
.analyze-form {
    max-width: 500px;
    margin: 40px auto;
}
.analyze-form input {
    width: 100%;
    padding: 10px 14px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--bg-tertiary);
    color: var(--text-primary);
    font-size: 14px;
    margin-bottom: 12px;
}
.hidden { display: none !important; }
/* Report view */
.report-content {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    font-size: 14px;
    line-height: 1.6;
    white-space: pre-wrap;
    font-family: -apple-system, BlinkMacSystemFont, monospace;
    max-height: calc(100vh - 280px);
    overflow-y: auto;
}
/* Donut chart */
.donut-chart {
    width: 160px;
    height: 160px;
    margin: 0 auto 20px;
}
/* Loading */
.loading { text-align: center; padding: 40px; color: var(--text-muted); }
.spinner {
    display: inline-block;
    width: 24px;
    height: 24px;
    border: 3px solid var(--border);
    border-top-color: var(--accent-blue);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
/* Topic tree */
.topic-tree { padding-left: 0; }
.topic-tree-item { list-style: none; }
.topic-tree-item .topic-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border-radius: 4px;
    cursor: pointer;
}
.topic-tree-item .topic-row:hover { background: var(--bg-tertiary); }
.topic-children { padding-left: 20px; }
/* Session list */
.session-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px;
    border-bottom: 1px solid rgba(51,65,85,0.5);
    cursor: pointer;
}
.session-item:hover { background: var(--bg-tertiary); }
</style>
</head>
<body>
<div class="app" id="app">
    <div class="header">
        <h1>DocZot Dashboard</h1>
        <span class="product-name" id="productName"></span>
        <div class="actions">
            <button class="btn" onclick="showAnalyzeModal()">Analyze Repo</button>
            <button class="btn" onclick="loadSessionList()">Sessions</button>
        </div>
    </div>
    <div class="main">
        <div class="nav" id="nav">
            <div class="nav-item active" data-view="graph" onclick="switchView('graph')">
                <span class="nav-dot"></span> Graph
            </div>
            <div class="nav-item" data-view="checklist" onclick="switchView('checklist')">
                <span class="nav-dot"></span> Checklist
            </div>
            <div class="nav-item" data-view="inventory" onclick="switchView('inventory')">
                <span class="nav-dot"></span> Inventory
            </div>
            <div class="nav-item" data-view="drift" onclick="switchView('drift')">
                <span class="nav-dot"></span> Drift
            </div>
            <div class="nav-item" data-view="review" onclick="switchView('review')">
                <span class="nav-dot"></span> Review
            </div>
            <div class="nav-item" data-view="reports" onclick="switchView('reports')">
                <span class="nav-dot"></span> Reports
            </div>
        </div>
        <div class="content" id="content">
            <div id="view-landing">
                <div class="analyze-form">
                    <h2>Welcome to DocZot</h2>
                    <p style="color:var(--text-secondary);margin:12px 0 20px">
                        Analyze a repository to measure documentation coverage.
                    </p>
                    <input type="text" id="repoPathInput" placeholder="Repository path (e.g., /path/to/project)" />
                    <input type="text" id="productNameInput" placeholder="Product name (optional)" />
                    <button class="btn btn-primary" onclick="startAnalysis()" style="width:100%">
                        Analyze
                    </button>
                    <div id="analyzeStatus" style="margin-top:16px;text-align:center;color:var(--text-muted)"></div>
                    <div style="margin-top:24px">
                        <h3>Recent Sessions</h3>
                        <div id="recentSessions"></div>
                    </div>
                </div>
            </div>
            <div id="view-graph" class="hidden"></div>
            <div id="view-checklist" class="hidden"></div>
            <div id="view-inventory" class="hidden"></div>
            <div id="view-drift" class="hidden"></div>
            <div id="view-review" class="hidden"></div>
            <div id="view-reports" class="hidden"></div>
            <div id="view-sessions" class="hidden"></div>
        </div>
    </div>
    <div class="status-bar" id="statusBar">
        <span>Ready</span>
    </div>
</div>

<!-- Modal container -->
<div id="modalContainer"></div>

<script>
// ==========================================================================
// STATE
// ==========================================================================
let currentSession = null;
let currentView = 'landing';
let sessionData = {};
let graphData = null;
let checklistData = null;
let inventoryData = null;
let driftData = null;
let judgmentsData = [];

const API = '';

// ==========================================================================
// NAVIGATION
// ==========================================================================
function switchView(view) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    const navEl = document.querySelector(`.nav-item[data-view="${view}"]`);
    if (navEl) navEl.classList.add('active');

    document.querySelectorAll('.content > div').forEach(el => el.classList.add('hidden'));
    const viewEl = document.getElementById('view-' + view);
    if (viewEl) viewEl.classList.remove('hidden');
    currentView = view;

    if (currentSession) {
        if (view === 'graph') loadGraphView();
        else if (view === 'checklist') loadChecklistView();
        else if (view === 'inventory') loadInventoryView();
        else if (view === 'drift') loadDriftView();
        else if (view === 'review') loadReviewView();
        else if (view === 'reports') loadReportsView();
    }
}

// ==========================================================================
// ANALYSIS
// ==========================================================================
async function startAnalysis() {
    const repoPath = document.getElementById('repoPathInput').value.trim();
    if (!repoPath) return alert('Please enter a repository path');
    const productName = document.getElementById('productNameInput').value.trim() || null;

    document.getElementById('analyzeStatus').innerHTML = '<div class="spinner"></div><br>Analyzing...';

    try {
        const res = await fetch(API + '/api/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({repo_path: repoPath, product_name: productName})
        });
        const data = await res.json();
        pollAnalysis(data.session_id);
    } catch(e) {
        document.getElementById('analyzeStatus').textContent = 'Error: ' + e.message;
    }
}

async function pollAnalysis(sessionId) {
    const check = async () => {
        const res = await fetch(API + `/api/analyze/${sessionId}/status`);
        const data = await res.json();
        if (data.status === 'complete') {
            document.getElementById('analyzeStatus').textContent = 'Analysis complete!';
            loadSession(sessionId);
        } else if (data.status.startsWith('error')) {
            document.getElementById('analyzeStatus').textContent = data.status;
        } else {
            document.getElementById('analyzeStatus').innerHTML = '<div class="spinner"></div><br>Analyzing...';
            setTimeout(check, 2000);
        }
    };
    check();
}

function showAnalyzeModal() {
    switchView('landing');
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.content > div').forEach(el => el.classList.add('hidden'));
    document.getElementById('view-landing').classList.remove('hidden');
}

// ==========================================================================
// SESSION MANAGEMENT
// ==========================================================================
async function loadSession(sessionId) {
    currentSession = sessionId;
    try {
        const res = await fetch(API + `/api/sessions/${sessionId}`);
        sessionData = await res.json();
        document.getElementById('productName').textContent = sessionData.product_name || '';
        updateStatusBar();
        switchView('graph');
    } catch(e) {
        console.error('Failed to load session:', e);
    }
}

async function loadSessionList() {
    try {
        const res = await fetch(API + '/api/sessions');
        const sessions = await res.json();
        renderSessionList(sessions);
    } catch(e) {
        console.error(e);
    }
}

function renderSessionList(sessions) {
    document.querySelectorAll('.content > div').forEach(el => el.classList.add('hidden'));
    const el = document.getElementById('view-sessions');
    el.classList.remove('hidden');

    el.innerHTML = '<h2>Analysis Sessions</h2>';
    if (!sessions.length) {
        el.innerHTML += '<p style="color:var(--text-muted)">No sessions yet. Run an analysis first.</p>';
        return;
    }
    sessions.forEach(s => {
        el.innerHTML += `
            <div class="session-item" onclick="loadSession('${s.id}')">
                <div>
                    <strong>${s.product_name}</strong>
                    <div style="font-size:12px;color:var(--text-muted)">${s.repo_path}</div>
                </div>
                <div style="font-size:12px;color:var(--text-muted)">${new Date(s.created_at).toLocaleString()}</div>
            </div>`;
    });
}

function updateStatusBar() {
    const bar = document.getElementById('statusBar');
    if (!sessionData.drift_json) {
        bar.innerHTML = '<span>No analysis loaded</span>';
        return;
    }
    const drift = typeof sessionData.drift_json === 'string'
        ? JSON.parse(sessionData.drift_json) : sessionData.drift_json;
    const items = drift.drift_items || [];
    const complete = items.filter(i => i.status === 'complete').length;
    const partial = items.filter(i => i.status === 'partial').length;
    const missing = items.filter(i => i.status === 'missing').length;
    const total = items.length || 1;
    const pct = Math.round((complete + partial * 0.5) / total * 100);
    bar.innerHTML = `
        <span>Coverage: <strong>${pct}%</strong></span>
        <span style="color:var(--accent-green)">${complete} complete</span>
        <span style="color:var(--accent-yellow)">${partial} partial</span>
        <span style="color:var(--accent-red)">${missing} missing</span>
        <span style="color:var(--text-muted)">Session: ${currentSession}</span>
    `;
}

// ==========================================================================
// GRAPH VIEW
// ==========================================================================
async function loadGraphView() {
    const el = document.getElementById('view-graph');
    el.innerHTML = '<div class="loading"><div class="spinner"></div><br>Loading graph...</div>';
    try {
        const res = await fetch(API + `/api/sessions/${currentSession}/graph`);
        graphData = await res.json();
        renderGraph(el);
    } catch(e) {
        el.innerHTML = '<p>Failed to load graph: ' + e.message + '</p>';
    }
}

function renderGraph(el) {
    if (!graphData || !graphData.nodes || !graphData.nodes.length) {
        el.innerHTML = '<p style="color:var(--text-muted)">No graph data available.</p>';
        return;
    }

    const nodes = graphData.nodes;
    const edges = graphData.edges || [];

    // Stats
    const verbs = nodes.filter(n => n.type === 'verb');
    const nouns = nodes.filter(n => n.type === 'noun');
    const concepts = nodes.filter(n => n.type === 'concept');
    const constraints = nodes.filter(n => n.type === 'constraint');

    let html = `
        <h2>System Graph</h2>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-blue)">${verbs.length}</div><div class="stat-label">Verbs</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-purple)">${nouns.length}</div><div class="stat-label">Nouns</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-yellow)">${concepts.length}</div><div class="stat-label">Concepts</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-red)">${constraints.length}</div><div class="stat-label">Constraints</div></div>
            <div class="stat-card"><div class="stat-value">${edges.length}</div><div class="stat-label">Edges</div></div>
        </div>
        <div class="graph-container" id="graphSvgContainer"></div>
        <h3 style="margin-top:20px">All Nodes</h3>
        <table class="data-table">
            <thead><tr><th>Type</th><th>Name</th><th>HTTP</th><th>Source</th></tr></thead>
            <tbody>
    `;

    for (const node of nodes) {
        const typeClass = 'badge-' + node.type;
        const http = (node.http_method && node.http_path) ? `${node.http_method} ${node.http_path}` : '';
        const source = node.source_file ? `${node.source_file}:${node.source_line || ''}` : '';
        html += `<tr>
            <td><span class="badge ${typeClass}">${node.type}</span></td>
            <td>${esc(node.name)}</td>
            <td style="font-family:monospace;font-size:12px">${esc(http)}</td>
            <td style="font-size:12px;color:var(--text-muted)">${esc(source)}</td>
        </tr>`;
    }
    html += '</tbody></table>';
    el.innerHTML = html;

    renderGraphSvg(nodes, edges);
}

function renderGraphSvg(nodes, edges) {
    const container = document.getElementById('graphSvgContainer');
    if (!container) return;
    const W = container.clientWidth;
    const H = container.clientHeight || 500;

    // Simple force-directed layout
    const positions = {};
    const typeColors = {verb:'#3b82f6', noun:'#a855f7', concept:'#eab308', constraint:'#ef4444'};
    const nodeRadius = 6;

    // Group by type for layout
    const byType = {};
    nodes.forEach((n,i) => {
        if (!byType[n.type]) byType[n.type] = [];
        byType[n.type].push(n);
    });

    // Arrange in rows by type
    let y = 60;
    for (const [type, group] of Object.entries(byType)) {
        const spacing = Math.min(100, (W - 60) / (group.length + 1));
        group.forEach((n, i) => {
            positions[n.id] = {
                x: 30 + (i + 1) * spacing + (Math.random() - 0.5) * 20,
                y: y + (Math.random() - 0.5) * 20
            };
        });
        y += 120;
    }

    let svg = `<svg width="${W}" height="${Math.max(H, y + 40)}" xmlns="http://www.w3.org/2000/svg">`;
    // Edges
    for (const edge of edges) {
        const s = positions[edge.source_id];
        const t = positions[edge.target_id];
        if (s && t) {
            svg += `<line x1="${s.x}" y1="${s.y}" x2="${t.x}" y2="${t.y}" stroke="#334155" stroke-width="1" opacity="0.6"/>`;
        }
    }
    // Nodes
    for (const node of nodes) {
        const p = positions[node.id];
        if (!p) continue;
        const color = typeColors[node.type] || '#64748b';
        const label = node.name.length > 20 ? node.name.slice(0, 18) + '..' : node.name;
        svg += `<circle cx="${p.x}" cy="${p.y}" r="${nodeRadius}" fill="${color}" opacity="0.9"/>`;
        svg += `<text x="${p.x}" y="${p.y + nodeRadius + 12}" text-anchor="middle" fill="#94a3b8" font-size="10">${esc(label)}</text>`;
    }
    svg += '</svg>';
    container.innerHTML = svg;
}

// ==========================================================================
// CHECKLIST VIEW
// ==========================================================================
async function loadChecklistView() {
    const el = document.getElementById('view-checklist');
    el.innerHTML = '<div class="loading"><div class="spinner"></div><br>Loading checklist...</div>';
    try {
        const res = await fetch(API + `/api/sessions/${currentSession}/checklist`);
        checklistData = await res.json();
        renderChecklist(el);
    } catch(e) {
        el.innerHTML = '<p>Failed to load checklist: ' + e.message + '</p>';
    }
}

function renderChecklist(el) {
    const itm = checklistData.checklist || {};
    const custom = checklistData.custom_topics || [];
    const topics = itm.topics || [];

    let html = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
            <h2>Coverage Checklist</h2>
            <button class="btn btn-primary" onclick="showAddTopicModal()">+ Add Topic</button>
        </div>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value">${topics.length}</div><div class="stat-label">Auto Topics</div></div>
            <div class="stat-card"><div class="stat-value">${custom.length}</div><div class="stat-label">Custom Topics</div></div>
        </div>
    `;

    // Render topic tree
    const roots = topics.filter(t => !t.parent_id);
    html += '<div class="topic-tree">';
    for (const root of roots) {
        html += renderTopicNode(root, topics);
    }
    html += '</div>';

    // Custom topics
    if (custom.length) {
        html += '<h3 style="margin-top:20px">Custom Topics</h3>';
        for (const ct of custom) {
            html += `<div class="card">
                <div class="card-header">
                    <span class="card-title">${esc(ct.name)}</span>
                    <div>
                        <span class="badge badge-task">${ct.topic_type}</span>
                        <button class="btn btn-sm" onclick="deleteCustomTopic('${ct.id}')" style="margin-left:8px;color:var(--accent-red)">Delete</button>
                    </div>
                </div>
                ${ct.description ? `<div style="font-size:13px;color:var(--text-secondary)">${esc(ct.description)}</div>` : ''}
            </div>`;
        }
    }

    el.innerHTML = html;
}

function renderTopicNode(topic, allTopics) {
    const children = allTopics.filter(t => t.parent_id === topic.id);
    const typeClass = topic.topic_type ? 'badge-' + topic.topic_type : '';
    const coverCount = (topic.covers || []).length;

    let html = `<div class="topic-tree-item">
        <div class="topic-row">
            ${children.length ? '<span style="color:var(--text-muted)">&#9654;</span>' : '<span style="width:12px"></span>'}
            <span class="badge ${typeClass}">${topic.topic_type || 'ref'}</span>
            <span>${esc(topic.name)}</span>
            ${coverCount ? `<span style="font-size:11px;color:var(--text-muted)">(${coverCount} nodes)</span>` : ''}
        </div>`;

    if (children.length) {
        html += '<div class="topic-children">';
        for (const child of children) {
            html += renderTopicNode(child, allTopics);
        }
        html += '</div>';
    }
    html += '</div>';
    return html;
}

function showAddTopicModal() {
    document.getElementById('modalContainer').innerHTML = `
        <div class="modal-overlay" onclick="closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()">
                <h3>Add Custom Topic</h3>
                <input type="text" id="topicName" placeholder="Topic name" />
                <select id="topicType">
                    <option value="task">Task (How-to)</option>
                    <option value="reference">Reference</option>
                    <option value="concept">Concept</option>
                    <option value="onboarding">Onboarding</option>
                </select>
                <textarea id="topicDesc" placeholder="Description (optional)"></textarea>
                <div class="modal-actions">
                    <button class="btn" onclick="closeModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="addCustomTopic()">Add</button>
                </div>
            </div>
        </div>`;
}

async function addCustomTopic() {
    const name = document.getElementById('topicName').value.trim();
    if (!name) return alert('Name is required');
    const type = document.getElementById('topicType').value;
    const desc = document.getElementById('topicDesc').value.trim() || null;

    await fetch(API + `/api/sessions/${currentSession}/checklist/topics`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, topic_type: type, description: desc})
    });
    closeModal();
    loadChecklistView();
}

async function deleteCustomTopic(topicId) {
    if (!confirm('Delete this topic?')) return;
    await fetch(API + `/api/sessions/${currentSession}/checklist/topics/${topicId}`, {method: 'DELETE'});
    loadChecklistView();
}

function closeModal(e) {
    if (e && e.target !== e.currentTarget) return;
    document.getElementById('modalContainer').innerHTML = '';
}

// ==========================================================================
// INVENTORY VIEW
// ==========================================================================
async function loadInventoryView() {
    const el = document.getElementById('view-inventory');
    el.innerHTML = '<div class="loading"><div class="spinner"></div><br>Loading inventory...</div>';
    try {
        const res = await fetch(API + `/api/sessions/${currentSession}/inventory`);
        inventoryData = await res.json();
        const jRes = await fetch(API + `/api/sessions/${currentSession}/judgments`);
        judgmentsData = await jRes.json();
        renderInventory(el);
    } catch(e) {
        el.innerHTML = '<p>Failed to load inventory: ' + e.message + '</p>';
    }
}

function renderInventory(el) {
    const topics = inventoryData.topics || [];
    const quality = inventoryData.quality || {};

    let html = `<h2>Content Inventory</h2>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value">${topics.length}</div><div class="stat-label">Doc Topics</div></div>
        </div>`;

    for (const topic of topics) {
        const q = quality[topic.id] || {};
        const evidence = topic.match_evidence || [];
        const coverageScore = q.coverage_score ? Math.round(q.coverage_score * 100) : 0;

        html += `<div class="card">
            <div class="card-header">
                <span class="card-title">${esc(topic.name)}</span>
                <div>
                    <span class="badge badge-reference">${(topic.covers || []).length} nodes</span>
                    <span style="margin-left:8px;font-size:12px;color:var(--text-muted)">Quality: ${coverageScore}%</span>
                </div>
            </div>
            <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">${topic.source_file || ''}</div>`;

        // Quality indicators
        html += `<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">`;
        if (q.has_examples) html += '<span class="badge badge-complete">has examples</span>';
        if (q.has_description) html += '<span class="badge badge-complete">has description</span>';
        if (q.terminology_consistent) html += '<span class="badge badge-complete">terminology ok</span>';
        if (q.has_auth_requirements === 'yes') html += '<span class="badge badge-complete">auth docs</span>';
        html += '</div>';

        // Evidence
        for (let i = 0; i < evidence.length; i++) {
            const ev = evidence[i];
            const judgment = judgmentsData.find(j => j.node_id === ev.node_id && j.topic_id === topic.id);
            const judgeClass = judgment ? (judgment.judgment === 'accept' ? 'direct' : judgment.judgment === 'reject' ? '' : 'semantic') : ev.strategy;

            html += `<div class="evidence-card ${judgeClass}">
                <div style="display:flex;justify-content:space-between">
                    <span style="font-size:12px;font-weight:600">${esc(ev.node_id)}</span>
                    <span class="badge ${ev.strategy === 'direct_reference' ? 'badge-complete' : 'badge-partial'}">${ev.strategy}</span>
                </div>
                <div style="font-size:11px;color:var(--text-muted)">${esc(ev.match_detail)}</div>
                <div class="evidence-snippet">${esc(ev.doc_snippet || '')}</div>
                <div class="evidence-actions">
                    <button class="btn btn-sm btn-accept" onclick="judge('${esc(ev.node_id)}','${topic.id}','accept',${i})">Accept</button>
                    <button class="btn btn-sm btn-reject" onclick="judge('${esc(ev.node_id)}','${topic.id}','reject',${i})">Reject</button>
                    <button class="btn btn-sm" onclick="judge('${esc(ev.node_id)}','${topic.id}','unsure',${i})">Unsure</button>
                    ${judgment ? `<span style="font-size:11px;color:var(--text-muted);margin-left:8px">${judgment.judgment}</span>` : ''}
                </div>
            </div>`;
        }
        html += '</div>';
    }

    el.innerHTML = html;
}

async function judge(nodeId, topicId, judgment, evidenceIndex) {
    await fetch(API + `/api/sessions/${currentSession}/judgments`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({node_id: nodeId, topic_id: topicId, judgment, evidence_index: evidenceIndex})
    });
    loadInventoryView();
}

// ==========================================================================
// DRIFT VIEW
// ==========================================================================
async function loadDriftView() {
    const el = document.getElementById('view-drift');
    el.innerHTML = '<div class="loading"><div class="spinner"></div><br>Loading drift report...</div>';
    try {
        const res = await fetch(API + `/api/sessions/${currentSession}/drift`);
        driftData = await res.json();
        renderDrift(el);
    } catch(e) {
        el.innerHTML = '<p>Failed to load drift: ' + e.message + '</p>';
    }
}

function renderDrift(el) {
    const items = driftData.drift_items || [];
    const extra = driftData.extra_topics || [];
    const complete = items.filter(i => i.status === 'complete').length;
    const partial = items.filter(i => i.status === 'partial').length;
    const missing = items.filter(i => i.status === 'missing').length;
    const total = items.length || 1;
    const pct = Math.round((complete + partial * 0.5) / total * 100);

    let html = `<h2>Drift Report</h2>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-blue)">${pct}%</div><div class="stat-label">Coverage</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-green)">${complete}</div><div class="stat-label">Complete</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-yellow)">${partial}</div><div class="stat-label">Partial</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-red)">${missing}</div><div class="stat-label">Missing</div></div>
            <div class="stat-card"><div class="stat-value">${extra.length}</div><div class="stat-label">Extra</div></div>
        </div>`;

    // Filter buttons
    html += `<div style="display:flex;gap:8px;margin-bottom:16px">
        <button class="btn btn-sm" onclick="filterDrift('all')">All</button>
        <button class="btn btn-sm" onclick="filterDrift('missing')">Missing</button>
        <button class="btn btn-sm" onclick="filterDrift('partial')">Partial</button>
        <button class="btn btn-sm" onclick="filterDrift('complete')">Complete</button>
    </div>`;

    html += '<div id="driftItems">';
    for (const item of items.sort((a, b) => b.priority - a.priority)) {
        const statusClass = 'badge-' + item.status;
        html += `<div class="card drift-item" data-status="${item.status}">
            <div class="card-header">
                <span class="card-title">${esc(item.matrix_topic_name)}</span>
                <span class="badge ${statusClass}">${item.status}</span>
            </div>`;
        if (item.action) html += `<div style="font-size:13px;color:var(--text-secondary)">${esc(item.action)}</div>`;
        if (item.missing_node_ids && item.missing_node_ids.length) {
            html += `<div style="font-size:12px;color:var(--text-muted);margin-top:4px">Missing: ${item.missing_node_ids.map(esc).join(', ')}</div>`;
        }
        if (item.quality_issues && item.quality_issues.length) {
            html += `<div style="margin-top:4px">`;
            item.quality_issues.forEach(qi => {
                html += `<span class="badge badge-partial" style="margin:2px">${esc(qi)}</span>`;
            });
            html += '</div>';
        }
        html += '</div>';
    }
    html += '</div>';

    el.innerHTML = html;
}

function filterDrift(status) {
    document.querySelectorAll('.drift-item').forEach(el => {
        if (status === 'all' || el.dataset.status === status) {
            el.style.display = '';
        } else {
            el.style.display = 'none';
        }
    });
}

// ==========================================================================
// REVIEW VIEW
// ==========================================================================
async function loadReviewView() {
    const el = document.getElementById('view-review');
    el.innerHTML = '<div class="loading"><div class="spinner"></div><br>Loading review queue...</div>';
    try {
        const [invRes, jRes, progRes] = await Promise.all([
            fetch(API + `/api/sessions/${currentSession}/inventory`),
            fetch(API + `/api/sessions/${currentSession}/judgments`),
            fetch(API + `/api/sessions/${currentSession}/judgments/progress`)
        ]);
        inventoryData = await invRes.json();
        judgmentsData = await jRes.json();
        const progress = await progRes.json();
        renderReview(el, progress);
    } catch(e) {
        el.innerHTML = '<p>Failed to load review: ' + e.message + '</p>';
    }
}

function renderReview(el, progress) {
    const topics = inventoryData.topics || [];
    const judgedKeys = new Set(judgmentsData.map(j => `${j.node_id}::${j.topic_id}`));

    // Build queue of unjudged evidence
    const queue = [];
    for (const topic of topics) {
        for (let i = 0; i < (topic.match_evidence || []).length; i++) {
            const ev = topic.match_evidence[i];
            const key = `${ev.node_id}::${topic.id}`;
            queue.push({topic, evidence: ev, index: i, judged: judgedKeys.has(key)});
        }
    }

    const unjudged = queue.filter(q => !q.judged);

    let html = `<h2>Match Review</h2>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-blue)">${progress.progress}%</div><div class="stat-label">Reviewed</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-green)">${progress.accepted}</div><div class="stat-label">Accepted</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-red)">${progress.rejected}</div><div class="stat-label">Rejected</div></div>
            <div class="stat-card"><div class="stat-value">${unjudged.length}</div><div class="stat-label">Remaining</div></div>
        </div>`;

    if (!unjudged.length) {
        html += '<div class="card"><p style="text-align:center;color:var(--accent-green)">All evidence reviewed!</p></div>';
    } else {
        html += '<h3>Review Queue</h3>';
        for (const item of unjudged.slice(0, 20)) {
            const ev = item.evidence;
            html += `<div class="card">
                <div class="card-header">
                    <span class="card-title">${esc(ev.node_id)}</span>
                    <span class="badge ${ev.strategy === 'direct_reference' ? 'badge-complete' : 'badge-partial'}">${ev.strategy}</span>
                </div>
                <div style="font-size:12px;color:var(--text-muted)">Topic: ${esc(item.topic.name)} | ${esc(ev.match_detail)}</div>
                <div class="evidence-snippet">${esc(ev.doc_snippet || '')}</div>
                <div style="font-size:11px;color:var(--text-muted)">${esc(ev.doc_file || '')} > ${esc(ev.doc_section || '')}</div>
                <div class="evidence-actions" style="margin-top:8px">
                    <button class="btn btn-sm btn-accept" onclick="judgeAndRefresh('${esc(ev.node_id)}','${item.topic.id}','accept',${item.index})">Accept</button>
                    <button class="btn btn-sm btn-reject" onclick="judgeAndRefresh('${esc(ev.node_id)}','${item.topic.id}','reject',${item.index})">Reject</button>
                    <button class="btn btn-sm" onclick="judgeAndRefresh('${esc(ev.node_id)}','${item.topic.id}','unsure',${item.index})">Skip</button>
                </div>
            </div>`;
        }
        if (unjudged.length > 20) {
            html += `<p style="color:var(--text-muted);text-align:center">...and ${unjudged.length - 20} more</p>`;
        }
    }

    el.innerHTML = html;
}

async function judgeAndRefresh(nodeId, topicId, judgment, evidenceIndex) {
    await fetch(API + `/api/sessions/${currentSession}/judgments`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({node_id: nodeId, topic_id: topicId, judgment, evidence_index: evidenceIndex})
    });
    loadReviewView();
}

// ==========================================================================
// REPORTS VIEW
// ==========================================================================
async function loadReportsView() {
    const el = document.getElementById('view-reports');
    el.innerHTML = `<h2>Reports</h2>
        <div style="display:flex;gap:12px;margin-bottom:20px">
            <button class="btn btn-primary" onclick="loadReport('coverage')">Coverage Report</button>
            <button class="btn" onclick="loadReport('missing')">Missing Docs</button>
            <button class="btn" onclick="loadReport('sprint')">Sprint Plan</button>
        </div>
        <div id="reportContent" class="report-content" style="color:var(--text-muted)">Select a report to generate.</div>`;
}

async function loadReport(type) {
    const contentEl = document.getElementById('reportContent');
    contentEl.innerHTML = '<div class="spinner"></div> Generating...';
    try {
        const res = await fetch(API + `/api/sessions/${currentSession}/reports/${type}`);
        const data = await res.json();
        contentEl.textContent = data.markdown || 'No data available.';
    } catch(e) {
        contentEl.textContent = 'Error: ' + e.message;
    }
}

// ==========================================================================
// UTILITIES
// ==========================================================================
function esc(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ==========================================================================
// INIT
// ==========================================================================
(async function init() {
    // Load recent sessions
    try {
        const res = await fetch(API + '/api/sessions');
        const sessions = await res.json();
        const el = document.getElementById('recentSessions');
        if (sessions.length) {
            el.innerHTML = sessions.slice(0, 5).map(s =>
                `<div class="session-item" onclick="loadSession('${s.id}')">
                    <div><strong>${esc(s.product_name)}</strong><div style="font-size:11px;color:var(--text-muted)">${esc(s.repo_path)}</div></div>
                    <div style="font-size:11px;color:var(--text-muted)">${new Date(s.created_at).toLocaleString()}</div>
                </div>`
            ).join('');
        } else {
            el.innerHTML = '<p style="color:var(--text-muted);font-size:13px">No sessions yet.</p>';
        }
    } catch(e) {
        console.log('Could not load sessions:', e.message);
    }
})();
</script>
</body>
</html>"""
