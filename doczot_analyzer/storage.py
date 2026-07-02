"""SQLite storage for DocZot manifests.

Provides persistent storage for TopicManifest data with:
- Full manifest save/load with JSON serialization
- Query by product name, date, coverage
- History tracking for trend analysis
"""

import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from doczot_analyzer.manifest import TopicManifest
from doczot_analyzer.models_v2 import SystemGraph, SystemNode, SystemEdge, NodeType, EdgeType, ConfidenceLevel


DEFAULT_DB_PATH = ".doczot/manifests.db"


class ManifestStore:
    """SQLite-backed storage for TopicManifest objects."""

    def __init__(self, db_path: str | Path | None = None):
        """Initialize the store.

        Args:
            db_path: Path to SQLite database. Defaults to .doczot/manifests.db
        """
        if db_path is None:
            db_path = DEFAULT_DB_PATH

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        """Open a connection that commits on success and always closes.

        sqlite3's own context manager only manages the transaction, not
        the connection; unclosed connections keep the database file
        locked on Windows.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS manifests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    version TEXT,
                    generated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                    -- Summary stats for quick queries
                    total_topics INTEGER,
                    documented INTEGER,
                    coverage_percentage REAL,

                    -- Full manifest as JSON
                    manifest_json TEXT NOT NULL,

                    -- Index for common queries
                    UNIQUE(product_name, generated_at)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_product_name
                ON manifests(product_name)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_generated_at
                ON manifests(generated_at)
            """)

            # v3: System Graph persistence tables (tables keep "surface_" prefix for DB compatibility)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scans (
                    id TEXT PRIMARY KEY,
                    product_name TEXT NOT NULL,
                    scanned_at TEXT NOT NULL,
                    source_paths TEXT NOT NULL,
                    node_count INTEGER,
                    edge_count INTEGER,
                    metadata TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS surface_nodes (
                    scan_id TEXT NOT NULL,
                    id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    node_class TEXT DEFAULT 'user-facing',
                    source_file TEXT,
                    source_line INTEGER,
                    code_signature TEXT,
                    http_method TEXT,
                    http_path TEXT,
                    PRIMARY KEY (scan_id, id),
                    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS surface_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    confidence TEXT DEFAULT 'medium',
                    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
                )
            """)

            # Indexes for System Graph queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_scan_id
                ON surface_nodes(scan_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_node_type
                ON surface_nodes(type)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_edge_scan
                ON surface_edges(scan_id)
            """)

            # Dashboard: analysis sessions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    product_name TEXT NOT NULL,
                    repo_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    graph_scan_id TEXT,
                    itm_json TEXT,
                    atm_json TEXT,
                    drift_json TEXT,
                    doc_graph_json TEXT,
                    FOREIGN KEY (graph_scan_id) REFERENCES scans(id)
                )
            """)

            # Dashboard: user judgments on match evidence
            conn.execute("""
                CREATE TABLE IF NOT EXISTS judgments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    topic_id TEXT NOT NULL,
                    evidence_index INTEGER,
                    judgment TEXT NOT NULL,
                    notes TEXT,
                    judged_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id),
                    UNIQUE(session_id, node_id, topic_id)
                )
            """)

            # Dashboard: user-added topics
            conn.execute("""
                CREATE TABLE IF NOT EXISTS custom_topics (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    topic_type TEXT NOT NULL,
                    description TEXT,
                    covers TEXT,
                    parent_id TEXT,
                    priority INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_product
                ON sessions(product_name)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_judgment_session
                ON judgments(session_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_custom_topic_session
                ON custom_topics(session_id)
            """)

            # Validation framework: results
            conn.execute("""
                CREATE TABLE IF NOT EXISTS validation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    scan_id TEXT,
                    dimension TEXT NOT NULL,
                    check_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    details TEXT,
                    checked_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_validation_product
                ON validation_results(product_name)
            """)

            conn.commit()

    def save(self, manifest: TopicManifest) -> int:
        """Save a manifest to the database.

        Args:
            manifest: The manifest to save

        Returns:
            The database row ID
        """
        stats = manifest.coverage_stats()

        with self._connect() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO manifests
                (product_name, version, generated_at, total_topics,
                 documented, coverage_percentage, manifest_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                manifest.product_name,
                manifest.version,
                manifest.generated_at.isoformat(),
                stats.get("total_topics", 0),
                stats.get("documented", 0),
                stats.get("coverage_percentage", 0.0),
                json.dumps(manifest.model_dump(), default=str),
            ))
            conn.commit()
            return cursor.lastrowid

    def load(self, product_name: str, version: str | None = None) -> Optional[TopicManifest]:
        """Load the latest manifest for a product.

        Args:
            product_name: Name of the product
            version: Optional specific version to load

        Returns:
            The manifest if found, None otherwise
        """
        with self._connect() as conn:
            if version:
                cursor = conn.execute("""
                    SELECT manifest_json FROM manifests
                    WHERE product_name = ? AND version = ?
                    ORDER BY generated_at DESC
                    LIMIT 1
                """, (product_name, version))
            else:
                cursor = conn.execute("""
                    SELECT manifest_json FROM manifests
                    WHERE product_name = ?
                    ORDER BY generated_at DESC
                    LIMIT 1
                """, (product_name,))

            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                return TopicManifest.model_validate(data)
            return None

    def load_by_id(self, manifest_id: int) -> Optional[TopicManifest]:
        """Load a specific manifest by ID.

        Args:
            manifest_id: The database row ID

        Returns:
            The manifest if found, None otherwise
        """
        with self._connect() as conn:
            cursor = conn.execute("""
                SELECT manifest_json FROM manifests
                WHERE id = ?
            """, (manifest_id,))

            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                return TopicManifest.model_validate(data)
            return None

    def list_products(self) -> list[str]:
        """List all product names in the store.

        Returns:
            List of unique product names
        """
        with self._connect() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT product_name FROM manifests
                ORDER BY product_name
            """)
            return [row[0] for row in cursor.fetchall()]

    def list_manifests(
        self,
        product_name: str | None = None,
        limit: int = 20
    ) -> list[dict]:
        """List manifests with summary info.

        Args:
            product_name: Optional filter by product name
            limit: Maximum number of results

        Returns:
            List of manifest summaries
        """
        with self._connect() as conn:
            if product_name:
                cursor = conn.execute("""
                    SELECT id, product_name, version, generated_at,
                           total_topics, documented, coverage_percentage
                    FROM manifests
                    WHERE product_name = ?
                    ORDER BY generated_at DESC
                    LIMIT ?
                """, (product_name, limit))
            else:
                cursor = conn.execute("""
                    SELECT id, product_name, version, generated_at,
                           total_topics, documented, coverage_percentage
                    FROM manifests
                    ORDER BY generated_at DESC
                    LIMIT ?
                """, (limit,))

            return [
                {
                    "id": row[0],
                    "product_name": row[1],
                    "version": row[2],
                    "generated_at": row[3],
                    "total_topics": row[4],
                    "documented": row[5],
                    "coverage_percentage": row[6],
                }
                for row in cursor.fetchall()
            ]

    def get_history(
        self,
        product_name: str,
        limit: int = 30
    ) -> list[dict]:
        """Get coverage history for trend analysis.

        Args:
            product_name: Name of the product
            limit: Maximum number of data points

        Returns:
            List of {date, coverage, documented, total} dicts
        """
        with self._connect() as conn:
            cursor = conn.execute("""
                SELECT generated_at, coverage_percentage, documented, total_topics
                FROM manifests
                WHERE product_name = ?
                ORDER BY generated_at DESC
                LIMIT ?
            """, (product_name, limit))

            return [
                {
                    "date": row[0],
                    "coverage": row[1],
                    "documented": row[2],
                    "total": row[3],
                }
                for row in cursor.fetchall()
            ]

    def delete(self, manifest_id: int) -> bool:
        """Delete a manifest by ID.

        Args:
            manifest_id: The database row ID

        Returns:
            True if deleted, False if not found
        """
        with self._connect() as conn:
            cursor = conn.execute("""
                DELETE FROM manifests WHERE id = ?
            """, (manifest_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_product(self, product_name: str) -> int:
        """Delete all manifests for a product.

        Args:
            product_name: Name of the product

        Returns:
            Number of manifests deleted
        """
        with self._connect() as conn:
            cursor = conn.execute("""
                DELETE FROM manifests WHERE product_name = ?
            """, (product_name,))
            conn.commit()
            return cursor.rowcount

    # v3: System Graph persistence methods

    def save_system_graph(self, graph: SystemGraph) -> str:
        """Save a System Graph to the database.

        Args:
            graph: The SystemGraph to save

        Returns:
            The scan_id for reference
        """
        scan_id = f"{graph.product_name}:{graph.scanned_at.isoformat()}"

        with self._connect() as conn:
            # Save scan metadata
            conn.execute("""
                INSERT OR REPLACE INTO scans
                (id, product_name, scanned_at, source_paths, node_count, edge_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                scan_id,
                graph.product_name,
                graph.scanned_at.isoformat(),
                json.dumps(graph.source_paths),
                len(graph.nodes),
                len(graph.edges),
                json.dumps({"version": graph.version} if graph.version else {}),
            ))

            # Delete existing nodes and edges for this scan (if replacing)
            conn.execute("DELETE FROM surface_nodes WHERE scan_id = ?", (scan_id,))
            conn.execute("DELETE FROM surface_edges WHERE scan_id = ?", (scan_id,))

            # Save nodes (use INSERT OR IGNORE for safety in case of duplicates)
            for node in graph.nodes:
                conn.execute("""
                    INSERT OR IGNORE INTO surface_nodes
                    (id, scan_id, type, name, description, node_class, source_file,
                     source_line, code_signature, http_method, http_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    node.id,
                    scan_id,
                    node.type.value,
                    node.name,
                    node.description,
                    node.node_class.value,
                    node.source_file,
                    node.source_line,
                    node.code_signature,
                    node.http_method,
                    node.http_path,
                ))

            # Save edges
            for edge in graph.edges:
                conn.execute("""
                    INSERT INTO surface_edges
                    (scan_id, source_id, target_id, edge_type, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    scan_id,
                    edge.source_id,
                    edge.target_id,
                    edge.edge_type.value,
                    edge.confidence.value,
                ))

            conn.commit()

        return scan_id

    def load_system_graph(
        self,
        product_name: str,
        scan_id: Optional[str] = None
    ) -> Optional[SystemGraph]:
        """Load a System Graph from the database.

        Args:
            product_name: Name of the product
            scan_id: Optional specific scan ID. If None, loads latest.

        Returns:
            The SystemGraph if found, None otherwise
        """
        with self._connect() as conn:
            # Get scan metadata
            if scan_id:
                cursor = conn.execute("""
                    SELECT id, product_name, scanned_at, source_paths, metadata
                    FROM scans
                    WHERE id = ?
                """, (scan_id,))
            else:
                cursor = conn.execute("""
                    SELECT id, product_name, scanned_at, source_paths, metadata
                    FROM scans
                    WHERE product_name = ?
                    ORDER BY scanned_at DESC
                    LIMIT 1
                """, (product_name,))

            scan_row = cursor.fetchone()
            if not scan_row:
                return None

            scan_id = scan_row[0]
            product_name = scan_row[1]
            scanned_at = datetime.fromisoformat(scan_row[2])
            source_paths = json.loads(scan_row[3])
            metadata = json.loads(scan_row[4]) if scan_row[4] else {}

            # Load nodes
            cursor = conn.execute("""
                SELECT id, type, name, description, node_class, source_file,
                       source_line, code_signature, http_method, http_path
                FROM surface_nodes
                WHERE scan_id = ?
            """, (scan_id,))

            nodes = []
            for row in cursor.fetchall():
                node = SystemNode(
                    id=row[0],
                    type=NodeType(row[1]),
                    name=row[2],
                    description=row[3],
                    node_class=row[4],
                    source_file=row[5],
                    source_line=row[6],
                    code_signature=row[7],
                    http_method=row[8],
                    http_path=row[9],
                )
                nodes.append(node)

            # Load edges
            cursor = conn.execute("""
                SELECT source_id, target_id, edge_type, confidence
                FROM surface_edges
                WHERE scan_id = ?
            """, (scan_id,))

            edges = []
            for row in cursor.fetchall():
                edge = SystemEdge(
                    source_id=row[0],
                    target_id=row[1],
                    edge_type=EdgeType(row[2]),
                    confidence=ConfidenceLevel(row[3]),
                )
                edges.append(edge)

            return SystemGraph(
                product_name=product_name,
                version=metadata.get("version"),
                scanned_at=scanned_at,
                source_paths=source_paths,
                nodes=nodes,
                edges=edges,
            )

    def list_scans(self, product_name: Optional[str] = None) -> list[dict]:
        """List available scans.

        Args:
            product_name: Optional filter by product name

        Returns:
            List of scan summaries
        """
        with self._connect() as conn:
            if product_name:
                cursor = conn.execute("""
                    SELECT id, product_name, scanned_at, node_count, edge_count
                    FROM scans
                    WHERE product_name = ?
                    ORDER BY scanned_at DESC
                """, (product_name,))
            else:
                cursor = conn.execute("""
                    SELECT id, product_name, scanned_at, node_count, edge_count
                    FROM scans
                    ORDER BY scanned_at DESC
                """)

            return [
                {
                    "scan_id": row[0],
                    "product_name": row[1],
                    "scanned_at": row[2],
                    "node_count": row[3],
                    "edge_count": row[4],
                }
                for row in cursor.fetchall()
            ]

    def delete_scan(self, scan_id: str) -> bool:
        """Delete a scan and all its nodes/edges.

        Args:
            scan_id: The scan ID to delete

        Returns:
            True if deleted, False if not found
        """
        with self._connect() as conn:
            cursor = conn.execute("""
                DELETE FROM scans WHERE id = ?
            """, (scan_id,))
            conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # Dashboard: Session management
    # =========================================================================

    def save_session(self, session_data: dict) -> str:
        """Save an analysis session.

        Args:
            session_data: Dict with keys: id, product_name, repo_path,
                          created_at, graph_scan_id, itm_json, atm_json,
                          drift_json, doc_graph_json

        Returns:
            The session ID
        """
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions
                (id, product_name, repo_path, created_at, graph_scan_id,
                 itm_json, atm_json, drift_json, doc_graph_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_data["id"],
                session_data["product_name"],
                session_data["repo_path"],
                session_data["created_at"],
                session_data.get("graph_scan_id"),
                session_data.get("itm_json"),
                session_data.get("atm_json"),
                session_data.get("drift_json"),
                session_data.get("doc_graph_json"),
            ))
            conn.commit()
        return session_data["id"]

    def load_session(self, session_id: str) -> Optional[dict]:
        """Load a session by ID.

        Returns:
            Session dict or None if not found
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def list_sessions(self, product_name: Optional[str] = None) -> list[dict]:
        """List analysis sessions.

        Args:
            product_name: Optional filter by product name

        Returns:
            List of session summary dicts
        """
        with self._connect() as conn:
            if product_name:
                cursor = conn.execute("""
                    SELECT id, product_name, repo_path, created_at, graph_scan_id
                    FROM sessions
                    WHERE product_name = ?
                    ORDER BY created_at DESC
                """, (product_name,))
            else:
                cursor = conn.execute("""
                    SELECT id, product_name, repo_path, created_at, graph_scan_id
                    FROM sessions
                    ORDER BY created_at DESC
                """)

            return [
                {
                    "id": row[0],
                    "product_name": row[1],
                    "repo_path": row[2],
                    "created_at": row[3],
                    "graph_scan_id": row[4],
                }
                for row in cursor.fetchall()
            ]

    # =========================================================================
    # Dashboard: Judgments
    # =========================================================================

    def save_judgment(
        self,
        session_id: str,
        node_id: str,
        topic_id: str,
        judgment: str,
        notes: Optional[str] = None,
        evidence_index: Optional[int] = None,
    ) -> None:
        """Save a user judgment on a match.

        Args:
            session_id: Session ID
            node_id: System graph node being judged
            topic_id: ATM topic ID
            judgment: "accept", "reject", or "unsure"
            notes: Optional reviewer notes
            evidence_index: Which evidence item (optional)
        """
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO judgments
                (session_id, node_id, topic_id, evidence_index, judgment, notes, judged_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                node_id,
                topic_id,
                evidence_index,
                judgment,
                notes,
                datetime.now().isoformat(),
            ))
            conn.commit()

    def load_judgments(self, session_id: str) -> list[dict]:
        """Load all judgments for a session.

        Returns:
            List of judgment dicts
        """
        with self._connect() as conn:
            cursor = conn.execute("""
                SELECT id, session_id, node_id, topic_id, evidence_index,
                       judgment, notes, judged_at
                FROM judgments
                WHERE session_id = ?
                ORDER BY judged_at DESC
            """, (session_id,))

            return [
                {
                    "id": row[0],
                    "session_id": row[1],
                    "node_id": row[2],
                    "topic_id": row[3],
                    "evidence_index": row[4],
                    "judgment": row[5],
                    "notes": row[6],
                    "judged_at": row[7],
                }
                for row in cursor.fetchall()
            ]

    # =========================================================================
    # Dashboard: Custom topics
    # =========================================================================

    def save_custom_topic(self, session_id: str, topic_data: dict) -> str:
        """Save a user-created custom topic.

        Args:
            session_id: Session ID
            topic_data: Dict with keys: id, name, topic_type, description,
                        covers, parent_id, priority

        Returns:
            The topic ID
        """
        topic_id = topic_data["id"]
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO custom_topics
                (id, session_id, name, topic_type, description, covers,
                 parent_id, priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                topic_id,
                session_id,
                topic_data["name"],
                topic_data.get("topic_type", "task"),
                topic_data.get("description"),
                json.dumps(topic_data.get("covers", [])),
                topic_data.get("parent_id"),
                topic_data.get("priority", 0),
                datetime.now().isoformat(),
            ))
            conn.commit()
        return topic_id

    def load_custom_topics(self, session_id: str) -> list[dict]:
        """Load all custom topics for a session.

        Returns:
            List of custom topic dicts
        """
        with self._connect() as conn:
            cursor = conn.execute("""
                SELECT id, session_id, name, topic_type, description,
                       covers, parent_id, priority, created_at
                FROM custom_topics
                WHERE session_id = ?
                ORDER BY priority DESC, created_at ASC
            """, (session_id,))

            return [
                {
                    "id": row[0],
                    "session_id": row[1],
                    "name": row[2],
                    "topic_type": row[3],
                    "description": row[4],
                    "covers": json.loads(row[5]) if row[5] else [],
                    "parent_id": row[6],
                    "priority": row[7],
                    "created_at": row[8],
                }
                for row in cursor.fetchall()
            ]

    def update_custom_topic(self, topic_id: str, updates: dict) -> bool:
        """Update a custom topic.

        Args:
            topic_id: The topic ID to update
            updates: Dict of field -> value to update

        Returns:
            True if updated, False if not found
        """
        allowed = {"name", "topic_type", "description", "covers", "parent_id", "priority"}
        set_clauses = []
        params = []
        for key, value in updates.items():
            if key in allowed:
                if key == "covers":
                    value = json.dumps(value)
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return False

        params.append(topic_id)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE custom_topics SET {', '.join(set_clauses)} WHERE id = ?",
                params,
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_custom_topic(self, topic_id: str) -> bool:
        """Delete a custom topic.

        Returns:
            True if deleted, False if not found
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM custom_topics WHERE id = ?", (topic_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    # Backward compatibility aliases for method names
    save_surface_graph = save_system_graph
    load_surface_graph = load_system_graph
