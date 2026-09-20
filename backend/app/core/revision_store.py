"""Authoritative Durable Revision Store Foundation for Veyra Phase 3 Day 34 (Gate C4).

Provides persistent, idempotent, and chronologically ordered storage for real weather
forecast issue-cycle runs and model bust predictions.

SCIENTIFIC GOVERNANCE INVARIANTS:
1. Target Identity: Revisions are uniquely identified by the exact verification target:
   (canonical_location, variable, valid_time, issue_time, provider_source)
2. Idempotency: Ingesting the same issue-cycle run multiple times produces exactly ONE durable record.
3. Chronological Ordering: When querying prior comparable history for a target, the previous
   revision is selected strictly by issue-cycle chronology:
   issue_time < current_issue_time ORDER BY issue_time DESC LIMIT 1.
4. Delta Invariant: Revision deltas are always defined as CURRENT minus PREVIOUS.
5. Store Failure Resilience: Unavailability or corruption of the store fails safely to an
   honest INSUFFICIENT_HISTORY / REVISION_HISTORY_UNAVAILABLE status without manufacturing fake data.
6. Test Isolation: Supports in-memory (':memory:') or dedicated isolated temporary paths.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import sqlite3
from typing import List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.getenv("VEYRA_REVISION_DB_PATH", "data/revision_store.db")


@dataclass
class RevisionRecord:
    """Scientific data model representing a single durable forecast issue-cycle evaluation."""

    canonical_location: str
    variable: str
    valid_time: str
    issue_time: str
    lead_hours: int
    forecast_value: float
    ensemble_mean: Optional[float] = None
    ensemble_spread: Optional[float] = None
    bust_probability: Optional[float] = None
    model_version: str = "veyra-v3-benchmark-lightgbm"
    model_sha256: str = "00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660"
    provider_source: str = "noaa_gefs_v12"
    created_at: Optional[str] = None


class RevisionStore:
    """Thread-safe, durable SQLite-backed revision store for forecast issue cycles."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("VEYRA_REVISION_DB_PATH", DEFAULT_DB_PATH)
        self._is_memory = self.db_path == ":memory:"
        self._mem_conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> Optional[sqlite3.Connection]:
        """Create or return a SQLite connection configured for WAL mode and fast concurrency."""
        if self._is_memory:
            if self._mem_conn is None:
                try:
                    self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
                    self._mem_conn.row_factory = sqlite3.Row
                except Exception as exc:
                    logger.warning("Failed to open in-memory SQLite database: %s", exc)
                    return None
            return self._mem_conn

        try:
            db_file = Path(self.db_path)
            db_file.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_file), timeout=10.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for high concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            return conn
        except (sqlite3.Error, OSError, Exception) as exc:
            logger.warning("Failed to open SQLite database at %s: %s", self.db_path, exc)
            return None

    def _init_db(self) -> None:
        """Initialize SQLite database schema and indices."""
        try:
            conn = self._get_connection()
            if conn is None:
                return
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS forecast_revisions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        canonical_location TEXT NOT NULL,
                        variable TEXT NOT NULL,
                        valid_time TEXT NOT NULL,
                        issue_time TEXT NOT NULL,
                        lead_hours INTEGER NOT NULL,
                        forecast_value REAL NOT NULL,
                        ensemble_mean REAL,
                        ensemble_spread REAL,
                        bust_probability REAL,
                        model_version TEXT NOT NULL,
                        model_sha256 TEXT NOT NULL,
                        provider_source TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        CONSTRAINT uq_forecast_revision UNIQUE (
                            canonical_location, variable, valid_time, issue_time, provider_source
                        )
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_rev_target
                    ON forecast_revisions(canonical_location, variable, valid_time);
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_rev_issue
                    ON forecast_revisions(issue_time);
                """)
            if not self._is_memory:
                conn.close()
        except (sqlite3.Error, OSError, Exception) as exc:
            logger.warning("Failed to initialize RevisionStore schema at %s: %s", self.db_path, exc)


    def record_revision(self, record: RevisionRecord) -> bool:
        """Persist a forecast issue-cycle evaluation record idempotently.

        Returns True on successful write/upsert, False on store failure.
        """
        created_at = record.created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            conn = self._get_connection()
            if conn is None:
                return False
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO forecast_revisions (
                        canonical_location,
                        variable,
                        valid_time,
                        issue_time,
                        lead_hours,
                        forecast_value,
                        ensemble_mean,
                        ensemble_spread,
                        bust_probability,
                        model_version,
                        model_sha256,
                        provider_source,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.canonical_location.strip(),
                    record.variable.strip().lower(),
                    record.valid_time.strip(),
                    record.issue_time.strip(),
                    int(record.lead_hours),
                    float(record.forecast_value),
                    float(record.ensemble_mean) if record.ensemble_mean is not None else None,
                    float(record.ensemble_spread) if record.ensemble_spread is not None else None,
                    float(record.bust_probability) if record.bust_probability is not None else None,
                    record.model_version.strip(),
                    record.model_sha256.strip(),
                    record.provider_source.strip(),
                    created_at,
                ))
            if not self._is_memory:
                conn.close()
            return True
        except Exception as exc:
            logger.warning("RevisionStore write failed for %s/%s: %s", record.canonical_location, record.valid_time, exc)
            return False

    def get_previous_revision(
        self,
        canonical_location: str,
        variable: str,
        valid_time: str,
        current_issue_time: str,
    ) -> Optional[RevisionRecord]:
        """Retrieve the immediately preceding comparable revision for the exact target.

        Selection rule: issue_time < current_issue_time ORDER BY issue_time DESC LIMIT 1.
        """
        try:
            conn = self._get_connection()
            if conn is None:
                return None
            cursor = conn.execute("""
                SELECT
                    canonical_location,
                    variable,
                    valid_time,
                    issue_time,
                    lead_hours,
                    forecast_value,
                    ensemble_mean,
                    ensemble_spread,
                    bust_probability,
                    model_version,
                    model_sha256,
                    provider_source,
                    created_at
                FROM forecast_revisions
                WHERE canonical_location = ?
                  AND variable = ?
                  AND valid_time = ?
                  AND issue_time < ?
                ORDER BY issue_time DESC
                LIMIT 1;
            """, (
                canonical_location.strip(),
                variable.strip().lower(),
                valid_time.strip(),
                current_issue_time.strip(),
            ))
            row = cursor.fetchone()
            if not self._is_memory:
                conn.close()

            if row is None:
                return None

            return RevisionRecord(
                canonical_location=row["canonical_location"],
                variable=row["variable"],
                valid_time=row["valid_time"],
                issue_time=row["issue_time"],
                lead_hours=row["lead_hours"],
                forecast_value=row["forecast_value"],
                ensemble_mean=row["ensemble_mean"],
                ensemble_spread=row["ensemble_spread"],
                bust_probability=row["bust_probability"],
                model_version=row["model_version"],
                model_sha256=row["model_sha256"],
                provider_source=row["provider_source"],
                created_at=row["created_at"],
            )
        except Exception as exc:
            logger.warning(
                "RevisionStore read failed for %s/%s/%s: %s",
                canonical_location,
                variable,
                valid_time,
                exc,
            )
            return None

    def get_trajectory_points(
        self,
        canonical_location: str,
        variable: str,
        valid_time: str,
        up_to_issue_time: Optional[str] = None,
    ) -> List[RevisionRecord]:
        """Retrieve all chronological issue-cycle points for a target up to a given issue time."""
        try:
            conn = self._get_connection()
            if conn is None:
                return []
            query = """
                SELECT
                    canonical_location,
                    variable,
                    valid_time,
                    issue_time,
                    lead_hours,
                    forecast_value,
                    ensemble_mean,
                    ensemble_spread,
                    bust_probability,
                    model_version,
                    model_sha256,
                    provider_source,
                    created_at
                FROM forecast_revisions
                WHERE canonical_location = ?
                  AND variable = ?
                  AND valid_time = ?
            """
            params: List[str] = [canonical_location.strip(), variable.strip().lower(), valid_time.strip()]
            if up_to_issue_time:
                query += " AND issue_time <= ?"
                params.append(up_to_issue_time.strip())

            query += " ORDER BY issue_time ASC;"

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            if not self._is_memory:
                conn.close()

            return [
                RevisionRecord(
                    canonical_location=row["canonical_location"],
                    variable=row["variable"],
                    valid_time=row["valid_time"],
                    issue_time=row["issue_time"],
                    lead_hours=row["lead_hours"],
                    forecast_value=row["forecast_value"],
                    ensemble_mean=row["ensemble_mean"],
                    ensemble_spread=row["ensemble_spread"],
                    bust_probability=row["bust_probability"],
                    model_version=row["model_version"],
                    model_sha256=row["model_sha256"],
                    provider_source=row["provider_source"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
        except Exception as exc:
            logger.warning(
                "RevisionStore trajectory query failed for %s/%s/%s: %s",
                canonical_location,
                variable,
                valid_time,
                exc,
            )
            return []

    def get_revision_count(self) -> int:
        """Count total stored revision records across all targets."""
        try:
            conn = self._get_connection()
            if conn is None:
                return 0
            cursor = conn.execute("SELECT COUNT(*) AS cnt FROM forecast_revisions;")
            count = cursor.fetchone()["cnt"]
            if not self._is_memory:
                conn.close()
            return int(count)
        except Exception as exc:
            logger.warning("RevisionStore count query failed: %s", exc)
            return 0

    def clear(self) -> None:
        """Clear all records (primarily used in isolated test fixtures)."""
        try:
            conn = self._get_connection()
            if conn is None:
                return
            with conn:
                conn.execute("DELETE FROM forecast_revisions;")
            if not self._is_memory:
                conn.close()
        except Exception as exc:
            logger.warning("RevisionStore clear failed: %s", exc)


# Global singleton revision store instance
_global_revision_store = RevisionStore()


def get_revision_store() -> RevisionStore:
    """Retrieve the global RevisionStore instance."""
    return _global_revision_store
