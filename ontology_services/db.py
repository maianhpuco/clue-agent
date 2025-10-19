"""SQLite persistence layer for ontology MCP server."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Tuple

from .settings import STORE_ROOT

DB_PATH = Path(
    os.environ.get("ONTOLOGY_DB_PATH", STORE_ROOT / "ontology_cache.db")  # type: ignore[arg-type]
)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _ensure_path(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(_ensure_path(DB_PATH))
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def db_cursor(commit: bool = False) -> Iterator[sqlite3.Cursor]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        if commit:
            conn.commit()
    finally:
        conn.close()


def initialize_schema() -> None:
    with db_cursor(commit=True) as cur:
        cur.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                source TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                max_results INTEGER NOT NULL,
                args_json TEXT NOT NULL,
                requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER NOT NULL,
                title TEXT,
                url TEXT,
                published TEXT,
                license TEXT,
                snippet TEXT,
                payload_json TEXT,
                UNIQUE(search_id, title, url),
                FOREIGN KEY (search_id) REFERENCES searches(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER NOT NULL,
                extractor TEXT NOT NULL,
                keyword TEXT NOT NULL,
                content_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (search_id) REFERENCES searches(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_searches_keyword_source ON searches(keyword, source);
            CREATE INDEX IF NOT EXISTS idx_results_search_id ON results(search_id);
            CREATE INDEX IF NOT EXISTS idx_extractions_search_id ON extractions(search_id);
            """
        )
        cur.execute("PRAGMA table_info(searches)")
        columns = {row["name"] for row in cur.fetchall()}
        if "tool_name" not in columns:
            cur.execute("ALTER TABLE searches ADD COLUMN tool_name TEXT NOT NULL DEFAULT 'unknown'")


def insert_search(keyword: str, source: str, tool_name: str, max_results: int, args: Dict[str, Any]) -> int:
    payload = json.dumps(args, ensure_ascii=False)
    with db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO searches (keyword, source, tool_name, max_results, args_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (keyword, source, tool_name, max_results, payload),
        )
        return int(cur.lastrowid)


def bulk_insert_results(search_id: int, items: Iterable[Dict[str, Any]]) -> int:
    records = []
    for item in items:
        payload_json = json.dumps(item, ensure_ascii=False)
        records.append(
            (
                search_id,
                item.get("title") or "",
                item.get("url") or "",
                item.get("published") or "",
                item.get("license") or "",
                item.get("snippet") or "",
                payload_json,
            )
        )
    if not records:
        return 0
    with db_cursor(commit=True) as cur:
        cur.executemany(
            """
            INSERT OR IGNORE INTO results
                (search_id, title, url, published, license, snippet, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )
        return cur.rowcount


def list_searches(keyword: str, source: Optional[str] = None) -> Tuple[Dict[str, Any], ...]:
    query = """
        SELECT id, keyword, source, tool_name, max_results, args_json, requested_at
        FROM searches
        WHERE keyword = ?
    """
    params: Tuple[Any, ...]
    if source:
        query += " AND source = ?"
        params = (keyword, source)
    else:
        params = (keyword,)
    query += " ORDER BY requested_at DESC"
    with db_cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    searches = []
    for row in rows:
        searches.append(
            {
                "id": row["id"],
                "keyword": row["keyword"],
                "source": row["source"],
                "tool_name": row["tool_name"],
                "max_results": row["max_results"],
                "args": json.loads(row["args_json"]),
                "requested_at": row["requested_at"],
            }
        )
    return tuple(searches)


def get_search(search_id: int) -> Optional[Dict[str, Any]]:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT id, keyword, source, tool_name, max_results, args_json, requested_at
            FROM searches
            WHERE id = ?
            """,
            (search_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "keyword": row["keyword"],
        "source": row["source"],
        "tool_name": row["tool_name"],
        "max_results": row["max_results"],
        "args": json.loads(row["args_json"]),
        "requested_at": row["requested_at"],
    }


def list_results(search_id: int) -> Tuple[Dict[str, Any], ...]:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT title, url, published, license, snippet, payload_json
            FROM results
            WHERE search_id = ?
            ORDER BY id ASC
            """,
            (search_id,),
        )
        rows = cur.fetchall()
    results = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        payload.update(
            {
                "title": row["title"],
                "url": row["url"],
                "published": row["published"],
                "license": row["license"],
                "snippet": row["snippet"],
            }
        )
        results.append(payload)
    return tuple(results)


def insert_extraction(search_id: int, extractor: str, keyword: str, content: Dict[str, Any]) -> int:
    content_json = json.dumps(content, ensure_ascii=False)
    with db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO extractions (search_id, extractor, keyword, content_json)
            VALUES (?, ?, ?, ?)
            """,
            (search_id, extractor, keyword, content_json),
        )
        return int(cur.lastrowid)


def list_extractions(search_id: Optional[int] = None, keyword: Optional[str] = None) -> Tuple[Dict[str, Any], ...]:
    query = """
        SELECT id, search_id, extractor, keyword, content_json, created_at
        FROM extractions
        WHERE 1=1
    """
    params: list[Any] = []
    if search_id is not None:
        query += " AND search_id = ?"
        params.append(search_id)
    if keyword is not None:
        query += " AND keyword = ?"
        params.append(keyword)
    query += " ORDER BY created_at DESC"
    with db_cursor() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
    extractions = []
    for row in rows:
        extractions.append(
            {
                "id": row["id"],
                "search_id": row["search_id"],
                "extractor": row["extractor"],
                "keyword": row["keyword"],
                "content": json.loads(row["content_json"]),
                "created_at": row["created_at"],
            }
        )
    return tuple(extractions)


# Initialize schema on import
initialize_schema()


__all__ = [
    "DB_PATH",
    "get_connection",
    "initialize_schema",
    "insert_search",
    "bulk_insert_results",
    "get_search",
    "list_searches",
    "list_results",
    "insert_extraction",
    "list_extractions",
]
