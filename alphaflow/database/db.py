"""SQLite database — reports, filings, agent_runs tables."""
import asyncio
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "alphaflow.db"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id          TEXT PRIMARY KEY,
            ticker      TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'queued',
            current_step TEXT,
            summary     TEXT,
            pdf_path    TEXT,
            error       TEXT,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_runs (
            id          TEXT PRIMARY KEY,
            report_id   TEXT NOT NULL,
            step        TEXT NOT NULL,
            status      TEXT NOT NULL,
            started_at  TEXT NOT NULL,
            finished_at TEXT,
            FOREIGN KEY (report_id) REFERENCES reports(id)
        );
        """)


def create_report(ticker: str) -> str:
    report_id = f"rpt_{uuid.uuid4().hex[:8]}"
    with _conn() as conn:
        conn.execute(
            "INSERT INTO reports (id, ticker, status, created_at) VALUES (?, ?, 'queued', ?)",
            (report_id, ticker.upper(), datetime.utcnow().isoformat()),
        )
    return report_id


def get_report(report_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
    return dict(row) if row else None


async def update_report_step(report_id: str, step: str, status: str):
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute(
            "UPDATE reports SET status='processing', current_step=? "
            "WHERE id=? AND status NOT IN ('complete','error')",
            (step, report_id),
        )
        conn.execute(
            "INSERT OR REPLACE INTO agent_runs (id, report_id, step, status, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, report_id, step, status, now),
        )


async def update_report_result(report_id: str, pdf_path: str, summary: str):
    with _conn() as conn:
        conn.execute(
            "UPDATE reports SET status='complete', pdf_path=?, summary=?, current_step=NULL "
            "WHERE id=?",
            (pdf_path, summary, report_id),
        )


async def update_report_error(report_id: str, step: str, error: str):
    with _conn() as conn:
        conn.execute(
            "UPDATE reports SET status='error', error=?, current_step=? WHERE id=?",
            (error, step, report_id),
        )


# Initialise on import
init_db()
