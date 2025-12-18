"""SQLite storage for DocZot manifests.

Provides persistent storage for TopicManifest data with:
- Full manifest save/load with JSON serialization
- Query by product name, date, coverage
- History tracking for trend analysis
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from doczot_analyzer.manifest import TopicManifest


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

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
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

            conn.commit()

    def save(self, manifest: TopicManifest) -> int:
        """Save a manifest to the database.

        Args:
            manifest: The manifest to save

        Returns:
            The database row ID
        """
        stats = manifest.coverage_stats()

        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM manifests WHERE product_name = ?
            """, (product_name,))
            conn.commit()
            return cursor.rowcount
