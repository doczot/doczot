"""Tests for how far documentation discovery may reach.

Documentation legitimately sits above the code it describes — `docs/` at a
project root, code in `backend/app`. Reaching too far turns another product's
documentation into this one's coverage, which is how a fixture whose README
documented no endpoints came to report 98.3% coverage.
"""

import tempfile
from pathlib import Path

from doczot_analyzer.analyzer_v2 import (
    _ancestor_doc_files,
    discover_content_inventory,
    build_system_graph,
    find_doc_scope_root,
)


def _write(path: Path, content: str = "placeholder\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestFindDocScopeRoot:
    """The doc scope boundary is the enclosing project, not the git root."""

    def test_stops_at_nested_project_manifest(self):
        """A component with its own manifest does not inherit the outer repo.

        A monorepo holding several shipped packages must not let one package's
        documentation count toward another's coverage.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            _write(root / "pyproject.toml")
            _write(root / "README.md")

            component = root / "services" / "billing"
            _write(component / "pyproject.toml")
            _write(component / "app" / "main.py", "")

            scope = find_doc_scope_root(str(component / "app"))

            assert Path(scope) == component

    def test_ascends_to_project_root_when_code_is_nested(self):
        """The legitimate case: docs at the project root, code in a subdir."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            _write(root / "pyproject.toml")
            _write(root / "docs" / "api.md")
            _write(root / "backend" / "app" / "main.py", "")

            scope = find_doc_scope_root(str(root / "backend" / "app"))

            assert Path(scope) == root

    def test_falls_back_to_git_root_without_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            _write(root / "src" / "main.py", "")

            scope = find_doc_scope_root(str(root / "src"))

            assert Path(scope) == root


class TestAncestorDocFiles:
    """An ancestor contributes its own docs, not its whole subtree."""

    def test_excludes_sibling_subtrees(self):
        """Recursing down from an ancestor reaches sideways into siblings.

        Analyzing one fixture picked up a neighbouring fixture's README this
        way. A sibling's documentation says nothing about the code under
        analysis.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "README.md")
            _write(root / "docs" / "guide.md")
            _write(root / "sibling" / "README.md")
            _write(root / "sibling" / "nested" / "NOTES.md")

            found = {Path(p).resolve() for p in _ancestor_doc_files(str(root))}

            assert (root / "README.md").resolve() in found
            assert (root / "docs" / "guide.md").resolve() in found
            assert (root / "sibling" / "README.md").resolve() not in found
            assert (root / "sibling" / "nested" / "NOTES.md").resolve() not in found


class TestInventoryContainment:
    """End-to-end: coverage credit stays within the analyzed project."""

    def test_sibling_component_docs_are_not_credited(self):
        """Two components under one repo must not share coverage credit.

        Each has its own manifest, so each is its own doc scope. Without that
        boundary, the undocumented component inherits its neighbour's docs and
        reports coverage it has not earned.
        """
        app_source = '''
from fastapi import FastAPI

app = FastAPI()

@app.get("/widgets")
def list_widgets():
    """List widgets."""
    return []
'''
        neighbour_docs = """# Gadget Service

## List gadgets

`GET /gadgets` returns every gadget.

## Widgets

Widgets are the primary entity in this system, with an id and a name.
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()

            widget_svc = root / "services" / "widget"
            _write(widget_svc / "pyproject.toml")
            _write(widget_svc / "main.py", app_source)
            _write(widget_svc / "README.md", "# Widget Service\n\nInstall it.\n")

            gadget_svc = root / "services" / "gadget"
            _write(gadget_svc / "pyproject.toml")
            _write(gadget_svc / "README.md", neighbour_docs)

            graph = build_system_graph(str(widget_svc), "widget")
            inventory = discover_content_inventory(str(widget_svc), graph)

            sources = {
                Path(t.source_file).name
                for t in inventory.topics
                if t.source_file
            }
            gadget_readme = (gadget_svc / "README.md").resolve()
            resolved = {
                Path(t.source_file).resolve()
                for t in inventory.topics
                if t.source_file and Path(t.source_file).is_absolute()
            }

            assert gadget_readme not in resolved, (
                f"neighbouring component's docs credited: {sources}"
            )
