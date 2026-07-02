"""Tests for dashboard.py - FastAPI dashboard API endpoints."""
import json
import pytest
import tempfile
from datetime import datetime
from pathlib import Path

from doczot_analyzer.storage import ManifestStore
from doczot_analyzer.reports import (
    generate_coverage_report,
    generate_missing_docs_report,
    generate_sprint_plan,
)

# Try to import FastAPI test client
try:
    from fastapi.testclient import TestClient
    from doczot_analyzer.dashboard import create_app
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def tmp_db():
    """Create a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield str(db_path)


@pytest.fixture
def store(tmp_db):
    """Create a ManifestStore with temp DB."""
    return ManifestStore(tmp_db)


@pytest.fixture
def sample_session_data():
    """Sample session data for testing."""
    itm = {
        "manifest_type": "intended",
        "graph_id": "test:2024-01-01",
        "product_name": "test-api",
        "topics": [
            {"id": "t1", "name": "Users", "topic_type": "reference", "covers": ["verb:GET:/users"]},
            {"id": "t2", "name": "Projects", "topic_type": "reference", "covers": ["verb:GET:/projects"]},
        ],
    }
    atm = {
        "manifest_type": "actual",
        "graph_id": "test:2024-01-01",
        "product_name": "test-api",
        "topics": [
            {
                "id": "atm1",
                "name": "API Docs",
                "topic_type": "reference",
                "covers": ["verb:GET:/users"],
                "match_evidence": [
                    {
                        "node_id": "verb:GET:/users",
                        "strategy": "direct_reference",
                        "confidence": 1.0,
                        "doc_file": "docs/api.md",
                        "doc_section": "Users",
                        "doc_snippet": "GET /users returns all users",
                        "match_detail": "GET /users found in text",
                    }
                ],
            }
        ],
        "quality": {
            "atm1": {
                "has_parameters": "partial",
                "has_returns": "no",
                "has_errors": "no",
                "has_description": True,
                "has_examples": False,
                "coverage_score": 0.3,
            }
        },
    }
    drift = {
        "graph_id": "test-api",
        "matrix_id": "test:2024-01-01",
        "inventory_id": "test:2024-01-01",
        "product_name": "test-api",
        "drift_items": [
            {
                "matrix_topic_id": "t1",
                "matrix_topic_name": "Users",
                "inventory_topic_id": "atm1",
                "status": "complete",
                "missing_node_ids": [],
                "quality_issues": [],
                "action": "",
                "priority": 0,
            },
            {
                "matrix_topic_id": "t2",
                "matrix_topic_name": "Projects",
                "inventory_topic_id": None,
                "status": "missing",
                "missing_node_ids": ["verb:GET:/projects"],
                "quality_issues": [],
                "action": "Create new reference topic: Projects",
                "priority": 1,
            },
        ],
        "extra_topics": [],
    }

    return {
        "id": "session_test123",
        "product_name": "test-api",
        "repo_path": "/tmp/test-repo",
        "created_at": datetime.now().isoformat(),
        "graph_scan_id": None,
        "itm_json": json.dumps(itm),
        "atm_json": json.dumps(atm),
        "drift_json": json.dumps(drift),
        "doc_graph_json": None,
    }


# =============================================================================
# STORAGE TESTS (no FastAPI dependency)
# =============================================================================

def test_save_and_load_session(store, sample_session_data):
    """Test saving and loading a session."""
    store.save_session(sample_session_data)
    loaded = store.load_session("session_test123")

    assert loaded is not None
    assert loaded["product_name"] == "test-api"
    assert loaded["repo_path"] == "/tmp/test-repo"


def test_list_sessions(store, sample_session_data):
    """Test listing sessions."""
    store.save_session(sample_session_data)
    sessions = store.list_sessions()

    assert len(sessions) == 1
    assert sessions[0]["id"] == "session_test123"


def test_list_sessions_by_product(store, sample_session_data):
    """Test filtering sessions by product name."""
    store.save_session(sample_session_data)
    sessions = store.list_sessions(product_name="test-api")
    assert len(sessions) == 1

    sessions = store.list_sessions(product_name="nonexistent")
    assert len(sessions) == 0


def test_save_and_load_judgment(store, sample_session_data):
    """Test saving and loading judgments."""
    store.save_session(sample_session_data)

    store.save_judgment(
        session_id="session_test123",
        node_id="verb:GET:/users",
        topic_id="atm1",
        judgment="accept",
        notes="Looks correct",
    )

    judgments = store.load_judgments("session_test123")
    assert len(judgments) == 1
    assert judgments[0]["judgment"] == "accept"
    assert judgments[0]["notes"] == "Looks correct"


def test_judgment_upsert(store, sample_session_data):
    """Test that saving a judgment for the same node+topic replaces it."""
    store.save_session(sample_session_data)

    store.save_judgment("session_test123", "verb:GET:/users", "atm1", "accept")
    store.save_judgment("session_test123", "verb:GET:/users", "atm1", "reject")

    judgments = store.load_judgments("session_test123")
    assert len(judgments) == 1
    assert judgments[0]["judgment"] == "reject"


def test_save_and_load_custom_topic(store, sample_session_data):
    """Test custom topic CRUD."""
    store.save_session(sample_session_data)

    topic_id = store.save_custom_topic("session_test123", {
        "id": "custom_1",
        "name": "User Onboarding",
        "topic_type": "task",
        "description": "How to onboard new users",
        "covers": ["noun:user"],
        "priority": 5,
    })

    topics = store.load_custom_topics("session_test123")
    assert len(topics) == 1
    assert topics[0]["name"] == "User Onboarding"
    assert topics[0]["covers"] == ["noun:user"]


def test_update_custom_topic(store, sample_session_data):
    """Test updating a custom topic."""
    store.save_session(sample_session_data)
    store.save_custom_topic("session_test123", {
        "id": "custom_1",
        "name": "Old Name",
        "topic_type": "task",
    })

    ok = store.update_custom_topic("custom_1", {"name": "New Name", "priority": 10})
    assert ok

    topics = store.load_custom_topics("session_test123")
    assert topics[0]["name"] == "New Name"
    assert topics[0]["priority"] == 10


def test_delete_custom_topic(store, sample_session_data):
    """Test deleting a custom topic."""
    store.save_session(sample_session_data)
    store.save_custom_topic("session_test123", {
        "id": "custom_1",
        "name": "To Delete",
        "topic_type": "task",
    })

    ok = store.delete_custom_topic("custom_1")
    assert ok

    topics = store.load_custom_topics("session_test123")
    assert len(topics) == 0


# =============================================================================
# REPORT TESTS
# =============================================================================

def test_coverage_report(sample_session_data):
    """Test coverage report generation."""
    report = generate_coverage_report(sample_session_data)
    assert "Documentation Coverage Report" in report
    assert "test-api" in report
    assert "Complete Topics" in report
    assert "Users" in report
    assert "Projects" in report


def test_missing_docs_report(sample_session_data):
    """Test missing docs report generation."""
    report = generate_missing_docs_report(sample_session_data)
    assert "Missing Documentation" in report
    assert "Projects" in report
    assert "verb:GET:/projects" in report


def test_sprint_plan(sample_session_data):
    """Test sprint plan generation."""
    report = generate_sprint_plan(sample_session_data)
    assert "Sprint Plan" in report
    assert "Projects" in report
    assert "missing" in report


def test_report_with_empty_data():
    """Test reports handle empty/missing data gracefully."""
    empty_session = {
        "product_name": "empty",
        "drift_json": None,
        "itm_json": None,
        "atm_json": None,
    }
    # Should not crash
    assert generate_coverage_report(empty_session) is not None
    assert generate_missing_docs_report(empty_session) is not None
    assert generate_sprint_plan(empty_session) is not None


# =============================================================================
# API ENDPOINT TESTS (require FastAPI)
# =============================================================================

@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestDashboardAPI:
    """Tests for dashboard API endpoints."""

    @pytest.fixture
    def client(self, tmp_db, sample_session_data):
        """Create test client with pre-loaded session."""
        app = create_app(db_path=tmp_db)
        store = ManifestStore(tmp_db)
        store.save_session(sample_session_data)
        return TestClient(app)

    def test_serve_dashboard(self, client):
        """Test that the HTML dashboard is served."""
        res = client.get("/")
        assert res.status_code == 200
        assert "DocZot Dashboard" in res.text

    def test_list_sessions(self, client):
        """Test listing sessions."""
        res = client.get("/api/sessions")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["product_name"] == "test-api"

    def test_get_session(self, client):
        """Test getting a specific session."""
        res = client.get("/api/sessions/session_test123")
        assert res.status_code == 200
        data = res.json()
        assert data["product_name"] == "test-api"
        # JSON fields should be parsed
        assert isinstance(data["itm_json"], dict)

    def test_get_session_not_found(self, client):
        """Test 404 for missing session."""
        res = client.get("/api/sessions/nonexistent")
        assert res.status_code == 404

    def test_get_checklist(self, client):
        """Test getting coverage checklist."""
        res = client.get("/api/sessions/session_test123/checklist")
        assert res.status_code == 200
        data = res.json()
        assert "checklist" in data
        assert "custom_topics" in data

    def test_add_custom_topic(self, client):
        """Test adding a custom topic."""
        res = client.post("/api/sessions/session_test123/checklist/topics", json={
            "name": "My Custom Topic",
            "topic_type": "task",
            "description": "A test topic",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "created"
        assert data["id"].startswith("custom_")

    def test_delete_custom_topic(self, client):
        """Test deleting a custom topic."""
        # First create one
        res = client.post("/api/sessions/session_test123/checklist/topics", json={
            "name": "To Delete",
            "topic_type": "task",
        })
        topic_id = res.json()["id"]

        # Delete it
        res = client.delete(f"/api/sessions/session_test123/checklist/topics/{topic_id}")
        assert res.status_code == 200

    def test_get_inventory(self, client):
        """Test getting content inventory."""
        res = client.get("/api/sessions/session_test123/inventory")
        assert res.status_code == 200
        data = res.json()
        assert "topics" in data

    def test_save_judgment(self, client):
        """Test saving a judgment."""
        res = client.put("/api/sessions/session_test123/judgments", json={
            "node_id": "verb:GET:/users",
            "topic_id": "atm1",
            "judgment": "accept",
        })
        assert res.status_code == 200

    def test_get_judgments(self, client):
        """Test getting judgments."""
        # Save one first
        client.put("/api/sessions/session_test123/judgments", json={
            "node_id": "verb:GET:/users",
            "topic_id": "atm1",
            "judgment": "accept",
        })

        res = client.get("/api/sessions/session_test123/judgments")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["judgment"] == "accept"

    def test_judgment_progress(self, client):
        """Test judgment progress stats."""
        res = client.get("/api/sessions/session_test123/judgments/progress")
        assert res.status_code == 200
        data = res.json()
        assert "total_evidence" in data
        assert "progress" in data

    def test_get_drift(self, client):
        """Test getting drift report."""
        res = client.get("/api/sessions/session_test123/drift")
        assert res.status_code == 200
        data = res.json()
        assert "drift_items" in data

    def test_coverage_report_endpoint(self, client):
        """Test coverage report endpoint."""
        res = client.get("/api/sessions/session_test123/reports/coverage")
        assert res.status_code == 200
        data = res.json()
        assert "markdown" in data
        assert "Coverage Report" in data["markdown"]

    def test_missing_report_endpoint(self, client):
        """Test missing docs report endpoint."""
        res = client.get("/api/sessions/session_test123/reports/missing")
        assert res.status_code == 200
        data = res.json()
        assert "markdown" in data

    def test_sprint_report_endpoint(self, client):
        """Test sprint plan report endpoint."""
        res = client.get("/api/sessions/session_test123/reports/sprint")
        assert res.status_code == 200
        data = res.json()
        assert "markdown" in data

    def test_invalid_judgment_value(self, client):
        """Test that invalid judgment values are rejected."""
        res = client.put("/api/sessions/session_test123/judgments", json={
            "node_id": "verb:GET:/users",
            "topic_id": "atm1",
            "judgment": "invalid",
        })
        assert res.status_code == 400


# =============================================================================
# SHARED SESSION SAVING (CLI + dashboard)
# =============================================================================

class TestSaveAnalysisSession:
    """save_analysis_session is the shared path for CLI and dashboard,
    so CLI-run analyses show up in the dashboard's session list."""

    def _make_analysis(self, tmp_path):
        from doczot_analyzer.models_v2 import (
            SystemGraph, SystemNode, NodeType, NodeClass, ManifestType,
            TopicManifest, generate_default_itm, compute_drift_report,
        )
        graph = SystemGraph(
            product_name="test-api",
            source_paths=[str(tmp_path)],
            nodes=[SystemNode(
                id="verb:GET:/users", type=NodeType.VERB, name="get_users",
                node_class=NodeClass.USER_FACING,
                http_method="GET", http_path="/users",
            )],
        )
        itm = generate_default_itm(graph)
        atm = TopicManifest(
            manifest_type=ManifestType.ACTUAL,
            graph_id=itm.graph_id,
            product_name="test-api",
        )
        drift = compute_drift_report(graph, itm, atm)
        return graph, itm, atm, drift

    def test_session_is_saved_and_listed(self, store, tmp_path):
        from doczot_analyzer.analyzer_v2 import save_analysis_session

        graph, itm, atm, drift = self._make_analysis(tmp_path)
        session_id = save_analysis_session(
            store, str(tmp_path), graph, itm, atm, drift
        )

        sessions = store.list_sessions()
        assert [s["id"] for s in sessions] == [session_id]

        session = store.load_session(session_id)
        assert session["product_name"] == "test-api"
        assert session["graph_scan_id"]
        assert json.loads(session["itm_json"])["topics"]
        assert json.loads(session["drift_json"])["drift_items"]

        # Graph is retrievable via the scan id stored on the session
        loaded = store.load_system_graph(
            "test-api", scan_id=session["graph_scan_id"]
        )
        assert loaded is not None
        assert len(loaded.nodes) == 1

    def test_explicit_session_id_is_used(self, store, tmp_path):
        from doczot_analyzer.analyzer_v2 import save_analysis_session

        graph, itm, atm, drift = self._make_analysis(tmp_path)
        returned = save_analysis_session(
            store, str(tmp_path), graph, itm, atm, drift,
            session_id="session_fixed",
        )
        assert returned == "session_fixed"
        assert store.load_session("session_fixed") is not None
