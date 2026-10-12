"""
storage/database.py
─────────────────────────────────────────────────────────────────────────────
SQLite-backed persistence for experiments and samples.
"""

import sqlite3
import json
import datetime
from typing import Dict, Any, List, Optional
from contextlib import contextmanager


class ExperimentDB:
    """Thread-safe SQLite database for experiment metadata and samples."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    # ── schema ─────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._conn() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS experiments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at      TEXT NOT NULL,
                workload        TEXT NOT NULL,
                alloc_mb        REAL,
                duration_s      REAL,
                interval_s      REAL,
                random_seed     INTEGER,
                status          TEXT DEFAULT 'running',
                -- summary fields (filled on completion)
                initial_page_faults  INTEGER,
                final_page_faults    INTEGER,
                fault_delta          INTEGER,
                fault_rate           REAL,
                peak_working_set_mb  REAL,
                final_working_set_mb REAL,
                pagefile_usage_mb    REAL,
                available_ram_mb     REAL,
                interpretation       TEXT,
                summary_json         TEXT
            );

            CREATE TABLE IF NOT EXISTS samples (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                exp_id       INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
                seq          INTEGER NOT NULL,
                timestamp    TEXT,
                elapsed_s    REAL,
                page_fault_count   INTEGER,
                working_set_mb     REAL,
                virtual_mem_mb     REAL,
                available_ram_mb   REAL,
                system_memory_pct  REAL,
                extra_json         TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_samples_exp ON samples(exp_id);
            """)

    @contextmanager
    def _conn(self):
        con = sqlite3.connect(self.db_path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    # ── experiment CRUD ────────────────────────────────────────────────────

    def create_experiment(self, workload: str, alloc_mb: float,
                          duration_s: float, interval_s: float,
                          random_seed: Optional[int] = None,
                          status: str = "running") -> int:
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        with self._conn() as con:
            cur = con.execute(
                """INSERT INTO experiments
                   (created_at, workload, alloc_mb, duration_s, interval_s, random_seed, status)
                   VALUES (?,?,?,?,?,?,?)""",
                (ts, workload, alloc_mb, duration_s, interval_s, random_seed, status),
            )
            return cur.lastrowid

    def update_experiment_status(self, exp_id: int, status: str) -> None:
        with self._conn() as con:
            con.execute("UPDATE experiments SET status=? WHERE id=?", (status, exp_id))

    def update_experiment_summary(self, exp_id: int, summary: Dict[str, Any]) -> None:
        with self._conn() as con:
            con.execute(
                """UPDATE experiments SET
                   initial_page_faults=?, final_page_faults=?, fault_delta=?,
                   fault_rate=?, peak_working_set_mb=?, final_working_set_mb=?,
                   pagefile_usage_mb=?, available_ram_mb=?,
                   interpretation=?, summary_json=?
                   WHERE id=?""",
                (
                    summary.get("initial_page_faults"),
                    summary.get("final_page_faults"),
                    summary.get("fault_delta"),
                    summary.get("fault_rate"),
                    summary.get("peak_working_set_mb"),
                    summary.get("final_working_set_mb") or summary.get("post_release_ws_mb"),
                    summary.get("pagefile_usage_mb"),
                    summary.get("final_available_ram_mb"),
                    summary.get("interpretation"),
                    json.dumps(summary),
                    exp_id,
                ),
            )

    def get_experiment(self, exp_id: int) -> Optional[Dict[str, Any]]:
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM experiments WHERE id=?", (exp_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_experiments(self) -> List[Dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM experiments ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_experiment(self, exp_id: int) -> None:
        with self._conn() as con:
            con.execute("DELETE FROM experiments WHERE id=?", (exp_id,))

    # ── samples ────────────────────────────────────────────────────────────

    def add_sample(self, exp_id: int, sample: Dict[str, Any]) -> None:
        seq = self.get_sample_count(exp_id)
        # Extract known fields; store the rest in extra_json
        known = {
            "timestamp", "elapsed_s", "page_fault_count",
            "working_set_mb", "virtual_mem_mb",
            "available_ram_mb", "system_memory_pct",
        }
        extra = {k: v for k, v in sample.items() if k not in known}
        with self._conn() as con:
            con.execute(
                """INSERT INTO samples
                   (exp_id, seq, timestamp, elapsed_s, page_fault_count,
                    working_set_mb, virtual_mem_mb, available_ram_mb,
                    system_memory_pct, extra_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    exp_id, seq,
                    sample.get("timestamp"),
                    sample.get("elapsed_s"),
                    sample.get("page_fault_count"),
                    sample.get("working_set_mb"),
                    sample.get("virtual_mem_mb"),
                    sample.get("available_ram_mb"),
                    sample.get("system_memory_pct"),
                    json.dumps(extra) if extra else None,
                ),
            )

    def get_samples(self, exp_id: int) -> List[Dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM samples WHERE exp_id=? ORDER BY seq",
                (exp_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_sample_count(self, exp_id: int) -> int:
        with self._conn() as con:
            row = con.execute(
                "SELECT COUNT(*) as c FROM samples WHERE exp_id=?", (exp_id,)
            ).fetchone()
        return row["c"] if row else 0
