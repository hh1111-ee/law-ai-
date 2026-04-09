#!/usr/bin/env python
"""
Synchronous migration script: imports Excel data into PostgreSQL.
Designed to run as a Railway pre-deploy command (synchronous, no asyncpg).

Usage:
    python scripts/migrate_data.py
"""

import os
import sys
import logging

# ---------------------------------------------------------------------------
# Logging — all output is prefixed with [migrate_data] for easy log filtering
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[migrate_data] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolve DATABASE_URL early so we fail fast with a clear message
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    log.error("DATABASE_URL environment variable is not set — aborting.")
    sys.exit(1)


def normalize_database_url(url: str) -> str:
    """Return a DATABASE_URL that uses the synchronous psycopg driver.

    Railway typically provides a plain ``postgresql://`` URL.  SQLAlchemy
    needs an explicit driver scheme for synchronous use; we normalise to
    ``postgresql+psycopg`` (psycopg v3, which is available in the project).
    """
    lower = url.lower()
    # Already has an explicit sync driver — leave it alone.
    if "+psycopg2" in lower or "+psycopg" in lower:
        # Strip asyncpg if someone accidentally set it.
        if "+asyncpg" in lower:
            url = url.replace("+asyncpg", "+psycopg")
        return url
    # Async driver — swap to sync.
    if "+asyncpg" in lower:
        return url.replace("+asyncpg", "+psycopg")
    # Plain postgresql:// — insert psycopg driver.
    if lower.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    # postgres:// shorthand (common on Heroku/Railway).
    if lower.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


# ---------------------------------------------------------------------------
# Imports that may be absent — fail with a clear message rather than a
# confusing traceback deep inside SQLAlchemy or pandas.
# ---------------------------------------------------------------------------
try:
    import pandas as pd
except ImportError:
    log.error("pandas is not installed. Add it to requirements.txt.")
    sys.exit(1)

try:
    from sqlalchemy import create_engine, text
except ImportError:
    log.error("sqlalchemy is not installed. Add it to requirements.txt.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# DDL — create tables if they do not already exist (no ORM import needed)
# ---------------------------------------------------------------------------
CREATE_EXAMPLE_RELATION = """
CREATE TABLE IF NOT EXISTS example_relation (
    id           SERIAL PRIMARY KEY,
    case_number  VARCHAR(256) UNIQUE NOT NULL,
    url          VARCHAR(1024),
    summary      TEXT,
    keyword1     VARCHAR(128),
    keyword2     VARCHAR(128),
    keyword3     VARCHAR(128),
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_EXAMPLE_LEGAL = """
CREATE TABLE IF NOT EXISTS example_legal (
    id          SERIAL PRIMARY KEY,
    region      VARCHAR(128),
    url         VARCHAR(1024),
    title       VARCHAR(512),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
"""


def create_tables(conn) -> None:
    """Create migration target tables if they do not already exist."""
    log.info("Ensuring tables exist...")
    conn.execute(text(CREATE_EXAMPLE_RELATION))
    conn.execute(text(CREATE_EXAMPLE_LEGAL))
    log.info("Table check complete.")


# ---------------------------------------------------------------------------
# Data import helpers
# ---------------------------------------------------------------------------

def import_example_relation(conn, file_path: str) -> int:
    """Import case records from 案号.xlsx into example_relation."""
    if not os.path.exists(file_path):
        log.warning("Excel file not found, skipping: %s", file_path)
        return 0

    log.info("Reading case file: %s", file_path)
    try:
        df = pd.read_excel(file_path, sheet_name=0)
    except Exception as exc:
        log.error("Failed to read %s: %s", file_path, exc)
        return 0

    df = df.rename(columns={
        "案号":   "case_number",
        "链接":   "url",
        "摘要":   "summary",
        "关键词1": "keyword1",
        "关键词2": "keyword2",
        "关键词3": "keyword3",
    })

    required = {"case_number", "url", "summary", "keyword1", "keyword2", "keyword3"}
    missing = required - set(df.columns)
    if missing:
        log.error("案号.xlsx is missing expected columns: %s", missing)
        return 0

    df = df[list(required)].where(pd.notnull(df), None)
    df = df.drop_duplicates(subset=["case_number"])
    log.info("Rows to process (case records): %d", len(df))

    inserted = skipped = 0
    for _, row in df.iterrows():
        case_num = row["case_number"]
        if not case_num:
            continue
        exists = conn.execute(
            text("SELECT 1 FROM example_relation WHERE case_number = :cn"),
            {"cn": case_num},
        ).fetchone()
        if exists:
            skipped += 1
            continue
        conn.execute(
            text(
                "INSERT INTO example_relation "
                "(case_number, url, summary, keyword1, keyword2, keyword3) "
                "VALUES (:cn, :url, :summary, :k1, :k2, :k3)"
            ),
            {
                "cn":      case_num,
                "url":     row["url"],
                "summary": row["summary"],
                "k1":      row["keyword1"],
                "k2":      row["keyword2"],
                "k3":      row["keyword3"],
            },
        )
        inserted += 1

    log.info("example_relation: inserted=%d, skipped=%d", inserted, skipped)
    return inserted


def import_example_legal(conn, file_path: str) -> int:
    """Import legal regulation records from 地区.xlsx into example_legal."""
    if not os.path.exists(file_path):
        log.warning("Excel file not found, skipping: %s", file_path)
        return 0

    log.info("Reading legal file: %s", file_path)
    try:
        df = pd.read_excel(file_path, sheet_name=0)
    except Exception as exc:
        log.error("Failed to read %s: %s", file_path, exc)
        return 0

    df = df.rename(columns={
        "地区":   "region",
        "网页链接": "url",
        "法规名称": "title",
    })

    required = {"region", "url", "title"}
    missing = required - set(df.columns)
    if missing:
        log.error("地区.xlsx is missing expected columns: %s", missing)
        return 0

    df = df[list(required)]
    df = df[df["title"].notna()]
    # Convert NaN to None for region column (handles pandas float NaN)
    df["region"] = df["region"].apply(lambda x: None if pd.isna(x) else x)
    df = df.drop_duplicates(subset=["title", "region"])
    log.info("Rows to process (legal records): %d", len(df))

    inserted = skipped = 0
    for _, row in df.iterrows():
        title  = row["title"]
        region = row["region"]   # Now either string or None
        exists = conn.execute(
            text(
                "SELECT 1 FROM example_legal "
                "WHERE title = :title "
                "AND (region = :region OR (region IS NULL AND :region IS NULL))"
            ),
            {"title": title, "region": region},
        ).fetchone()
        if exists:
            skipped += 1
            continue
        conn.execute(
            text(
                "INSERT INTO example_legal (region, url, title) "
                "VALUES (:region, :url, :title)"
            ),
            {"region": region, "url": row["url"], "title": title},
        )
        inserted += 1

    log.info("example_legal: inserted=%d, skipped=%d", inserted, skipped)
    return inserted


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    db_url = normalize_database_url(DATABASE_URL)
    log.info(
        "Connecting with URL scheme: %s",
        db_url.split("@")[0].split("://")[0] + "://***@...",
    )

    try:
        engine = create_engine(db_url, echo=False, future=True)
    except Exception as exc:
        log.error("Failed to create database engine: %s", exc)
        return 1

    BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    case_file  = os.path.join(BASE_DIR, "数据", "案号.xlsx")
    legal_file = os.path.join(BASE_DIR, "数据", "地区.xlsx")

    try:
        with engine.begin() as conn:
            create_tables(conn)
            import_example_relation(conn, case_file)
            import_example_legal(conn, legal_file)
        log.info("Migration completed successfully.")
        return 0
    except Exception as exc:
        log.error("Migration failed: %s", exc, exc_info=True)
        return 1
    finally:
        try:
            engine.dispose()
            log.info("Connection pool disposed.")
        except Exception as exc:
            log.warning("Failed to dispose connection pool: %s", exc)


if __name__ == "__main__":
    sys.exit(main())