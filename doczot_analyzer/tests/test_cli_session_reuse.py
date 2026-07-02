"""Tests for CLI session reuse (_load_or_analyze).

surface/itm/atm/gaps/visualize should load the latest saved session for
a repo instead of re-running the whole analysis pipeline every time.
"""
import pytest

from doczot_analyzer import cli_v2
from doczot_analyzer.analyzer_v2 import save_analysis_session
from doczot_analyzer.models_v2 import (
    ManifestType,
    NodeClass,
    NodeType,
    SystemGraph,
    SystemNode,
    TopicManifest,
    compute_drift_report,
    generate_default_itm,
)
from doczot_analyzer.storage import ManifestStore


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    return tmp_path


def _make_analysis(repo):
    graph = SystemGraph(
        product_name="reuse-api",
        source_paths=[str(repo)],
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
        product_name="reuse-api",
    )
    drift = compute_drift_report(graph, itm, atm)
    return graph, itm, atm, drift


class TestLoadOrAnalyze:
    def test_reuses_saved_session_without_reanalyzing(self, repo, tmp_path, monkeypatch):
        db = str(tmp_path / "reuse.db")
        store = ManifestStore(db)
        save_analysis_session(store, str(repo), *_make_analysis(repo))

        def boom(*a, **kw):
            raise AssertionError("analyze_repository should not run on cache hit")
        monkeypatch.setattr(cli_v2, "analyze_repository", boom)

        graph, itm, atm, drift = cli_v2._load_or_analyze(str(repo), None, db)

        assert graph.product_name == "reuse-api"
        assert len(graph.nodes) == 1
        assert itm.topics
        assert drift.drift_items

    def test_fresh_flag_forces_reanalysis(self, repo, tmp_path, monkeypatch):
        db = str(tmp_path / "reuse.db")
        store = ManifestStore(db)
        save_analysis_session(store, str(repo), *_make_analysis(repo))

        calls = []
        def fake_analyze(repo_path, product_name=None):
            calls.append(repo_path)
            return _make_analysis(repo)
        monkeypatch.setattr(cli_v2, "analyze_repository", fake_analyze)

        cli_v2._load_or_analyze(str(repo), None, db, fresh=True)

        assert len(calls) == 1
        # The fresh run is saved as a new session
        assert len(store.list_sessions()) == 2

    def test_different_repo_path_misses_cache(self, repo, tmp_path, monkeypatch):
        db = str(tmp_path / "reuse.db")
        store = ManifestStore(db)
        save_analysis_session(store, str(repo), *_make_analysis(repo))

        other = tmp_path / "other-repo"
        other.mkdir()
        calls = []
        def fake_analyze(repo_path, product_name=None):
            calls.append(repo_path)
            return _make_analysis(other)
        monkeypatch.setattr(cli_v2, "analyze_repository", fake_analyze)

        cli_v2._load_or_analyze(str(other), None, db)

        assert len(calls) == 1
