#!/usr/bin/env python3
"""
SQLite persistence layer for SEO Drift Monitor.

Stores baselines and check results for comparing page states over time.
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlparse, urlencode, parse_qs

DB_DIR = os.path.expanduser("~/.claude/seo-drift")
DB_PATH = os.path.join(DB_DIR, "baselines.db")
SCREENSHOTS_DIR = os.path.join(DB_DIR, "screenshots")
REPORTS_DIR = os.path.join(DB_DIR, "reports")


def normalize_url(url: str) -> str:
    """Normalize a URL for consistent comparison and storage."""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    parsed = urlparse(url)
    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower() if parsed.hostname else ""
    # Strip default ports
    port = parsed.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    netloc = f"{host}:{port}" if port else host
    # Strip trailing slash from path
    path = parsed.path.rstrip("/") or "/"
    # Sort query params, strip utm_* tracking params
    params = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in sorted(params.items()) if not k.startswith("utm_")}
    query = urlencode(filtered, doseq=True) if filtered else ""
    normalized = f"{scheme}://{netloc}{path}"
    if query:
        normalized += f"?{query}"
    return normalized


def url_hash(url: str) -> str:
    """SHA256 hash of normalized URL."""
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()[:16]


def init_db():
    """Create database and tables if they don't exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS baselines (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            url             TEXT NOT NULL,
            url_hash        TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            html_hash       TEXT NOT NULL,
            title           TEXT,
            meta_description TEXT,
            canonical       TEXT,
            robots          TEXT,
            headings_json   TEXT NOT NULL,
            schema_json     TEXT NOT NULL,
            schema_hash     TEXT NOT NULL,
            og_json         TEXT NOT NULL,
            cwv_json        TEXT,
            screenshot_path TEXT,
            status_code     INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_baselines_url ON baselines(url_hash);
        CREATE INDEX IF NOT EXISTS idx_baselines_created ON baselines(created_at);

        CREATE TABLE IF NOT EXISTS checks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            baseline_id     INTEGER NOT NULL REFERENCES baselines(id),
            url             TEXT NOT NULL,
            checked_at      TEXT NOT NULL,
            diffs_json      TEXT NOT NULL,
            screenshot_path TEXT,
            report_path     TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_checks_baseline ON checks(baseline_id);
    """)
    conn.close()


def _connect():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_baseline(data: dict) -> int:
    """Save a baseline snapshot. Returns the baseline ID."""
    init_db()
    conn = _connect()
    cursor = conn.execute(
        """INSERT INTO baselines
           (url, url_hash, created_at, html_hash, title, meta_description,
            canonical, robots, headings_json, schema_json, schema_hash,
            og_json, cwv_json, screenshot_path, status_code)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["url"],
            data["url_hash"],
            data["created_at"],
            data["html_hash"],
            data.get("title"),
            data.get("meta_description"),
            data.get("canonical"),
            data.get("robots"),
            json.dumps(data["headings"]),
            json.dumps(data["schema"]),
            data["schema_hash"],
            json.dumps(data.get("open_graph", {})),
            json.dumps(data["cwv"]) if data.get("cwv") else None,
            data.get("screenshot_path"),
            data.get("status_code"),
        ),
    )
    conn.commit()
    baseline_id = cursor.lastrowid
    conn.close()
    return baseline_id


def get_latest_baseline(url: str) -> dict | None:
    """Get the most recent baseline for a URL."""
    init_db()
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM baselines WHERE url_hash = ? ORDER BY created_at DESC LIMIT 1",
        (url_hash(normalize_url(url)),),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_baseline(row)


def get_all_baselines(url: str) -> list[dict]:
    """Get all baselines for a URL, newest first."""
    init_db()
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM baselines WHERE url_hash = ? ORDER BY created_at DESC",
        (url_hash(normalize_url(url)),),
    ).fetchall()
    conn.close()
    return [_row_to_baseline(r) for r in rows]


def save_check(baseline_id: int, diffs: list, screenshot_path: str = None,
               report_path: str = None, url: str = "") -> int:
    """Save a check result. Returns the check ID."""
    init_db()
    conn = _connect()
    cursor = conn.execute(
        """INSERT INTO checks (baseline_id, url, checked_at, diffs_json,
           screenshot_path, report_path)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            baseline_id,
            url,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(diffs),
            screenshot_path,
            report_path,
        ),
    )
    conn.commit()
    check_id = cursor.lastrowid
    conn.close()
    return check_id


def get_check_history(url: str) -> list[dict]:
    """Get all checks for a URL with their diffs."""
    init_db()
    conn = _connect()
    rows = conn.execute(
        """SELECT c.*, b.created_at as baseline_date
           FROM checks c JOIN baselines b ON c.baseline_id = b.id
           WHERE b.url_hash = ?
           ORDER BY c.checked_at DESC""",
        (url_hash(normalize_url(url)),),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "baseline_id": r["baseline_id"],
            "baseline_date": r["baseline_date"],
            "checked_at": r["checked_at"],
            "diffs": json.loads(r["diffs_json"]),
            "screenshot_path": r["screenshot_path"],
            "report_path": r["report_path"],
        }
        for r in rows
    ]


def _row_to_baseline(row) -> dict:
    """Convert a database row to a baseline dict."""
    return {
        "id": row["id"],
        "url": row["url"],
        "url_hash": row["url_hash"],
        "created_at": row["created_at"],
        "html_hash": row["html_hash"],
        "title": row["title"],
        "meta_description": row["meta_description"],
        "canonical": row["canonical"],
        "robots": row["robots"],
        "headings": json.loads(row["headings_json"]),
        "schema": json.loads(row["schema_json"]),
        "schema_hash": row["schema_hash"],
        "open_graph": json.loads(row["og_json"]),
        "cwv": json.loads(row["cwv_json"]) if row["cwv_json"] else None,
        "screenshot_path": row["screenshot_path"],
        "status_code": row["status_code"],
    }


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
    print(f"Screenshots dir: {SCREENSHOTS_DIR}")
    print(f"Reports dir: {REPORTS_DIR}")
