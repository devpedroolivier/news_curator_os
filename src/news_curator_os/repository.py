from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import MonitoringSummary, PipelineRun, RecentRunSummary


class RunRepository:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    headline TEXT NOT NULL,
                    normalized_headline TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    llm_mode TEXT NOT NULL,
                    search_provider TEXT NOT NULL,
                    credibility_band TEXT NOT NULL,
                    confidence_score INTEGER NOT NULL,
                    evidence_count INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    rank_order INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    published_at TEXT,
                    description TEXT,
                    query TEXT,
                    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id) ON DELETE CASCADE
                );
                """
            )

    def save_run(self, run: PipelineRun) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pipeline_runs (
                    run_id, created_at, headline, normalized_headline, execution_mode,
                    llm_mode, search_provider, credibility_band, confidence_score,
                    evidence_count, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.created_at,
                    run.headline,
                    run.normalized_headline,
                    run.execution_mode,
                    run.llm_mode,
                    run.search_provider,
                    run.output.credibility_band,
                    run.output.confidence_score,
                    len(run.evidence),
                    json.dumps(run.model_dump(mode="json"), ensure_ascii=False),
                ),
            )
            for index, item in enumerate(run.evidence, start=1):
                connection.execute(
                    """
                    INSERT INTO evidences (
                        run_id, rank_order, source, title, url, published_at, description, query
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run.run_id,
                        index,
                        item.source,
                        item.title,
                        item.url,
                        item.published_at,
                        item.description,
                        item.query,
                    ),
                )
            for entry in run.audit:
                connection.execute(
                    """
                    INSERT INTO audit_events (run_id, stage, severity, message, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        run.run_id,
                        entry.stage,
                        entry.severity,
                        entry.message,
                        entry.created_at,
                    ),
                )

    def list_recent_runs(self, limit: int = 8) -> list[RecentRunSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, created_at, headline, credibility_band, confidence_score,
                       evidence_count, execution_mode, llm_mode
                FROM pipeline_runs
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            RecentRunSummary(
                run_id=row["run_id"],
                created_at=row["created_at"],
                headline=row["headline"],
                credibility_band=row["credibility_band"],
                confidence_score=row["confidence_score"],
                evidence_count=row["evidence_count"],
                execution_mode=row["execution_mode"],
                llm_mode=row["llm_mode"],
            )
            for row in rows
        ]

    def get_run(self, run_id: str) -> PipelineRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM pipeline_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return PipelineRun.model_validate(json.loads(row["payload_json"]))

    def get_monitoring_summary(self, *, search_provider: str, openai_enabled: bool) -> MonitoringSummary:
        self.initialize()
        with self._connect() as connection:
            total_runs = connection.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
            runs_with_evidence = connection.execute(
                "SELECT COUNT(*) FROM pipeline_runs WHERE evidence_count > 0"
            ).fetchone()[0]
            degraded_runs = connection.execute(
                "SELECT COUNT(*) FROM pipeline_runs WHERE execution_mode LIKE '%degraded%'"
            ).fetchone()[0]
            latest_run = connection.execute(
                "SELECT created_at FROM pipeline_runs ORDER BY datetime(created_at) DESC LIMIT 1"
            ).fetchone()

        return MonitoringSummary(
            status="ok" if self.db_path.exists() else "degraded",
            database_ready=self.db_path.exists(),
            total_runs=total_runs,
            runs_with_evidence=runs_with_evidence,
            degraded_runs=degraded_runs,
            latest_run_at=latest_run["created_at"] if latest_run else None,
            search_provider=search_provider,
            openai_enabled=openai_enabled,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
