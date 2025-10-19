#!/usr/bin/env python3
"""Utility to list tables and show the five most recent rows in the ontology SQLite cache."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ontology_services.db import DB_PATH, get_connection  # noqa: E402


def resolve_order_column(columns: Iterable[str]) -> Optional[str]:
    priority = ["requested_at", "created_at", "updated_at", "id", "rowid"]
    for candidate in priority:
        if candidate in columns:
            return candidate
    return None


def maybe_parse_json(value: Any) -> Any:
    if isinstance(value, str) and value and value.strip().startswith(("{", "[")):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def query_table(conn: sqlite3.Connection, table: str, limit: int = 5) -> list[dict[str, Any]]:
    info_cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in info_cursor.fetchall()]
    order_column = resolve_order_column(columns)
    order_clause = f"ORDER BY {order_column} DESC" if order_column else ""
    cursor = conn.execute(f"SELECT * FROM {table} {order_clause} LIMIT ?", (limit,))
    rows = cursor.fetchall()
    records = []
    for row in rows:
        record = {}
        for idx in range(len(columns)):
            record[columns[idx]] = maybe_parse_json(row[idx])
        records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect ontology SQLite cache tables.")
    parser.add_argument(
        "table",
        nargs="?",
        help="Optional table name to query explicitly (e.g., searches, results, extractions).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of rows to return per table (default: 5).",
    )
    args = parser.parse_args()

    path = Path(os.environ.get("ONTOLOGY_DB_PATH", DB_PATH))
    if not path.exists():
        raise SystemExit(f"Database not found at {path}")

    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        if not tables:
            print("No tables found.")
            return

        if args.table:
            if args.table not in tables:
                raise SystemExit(f"Unknown table '{args.table}'. Available tables: {', '.join(tables)}")
            tables = [args.table]
            print(f"Database: {path.resolve()}")
            print(f"Table: {args.table}\n")
        else:
            print(f"Database: {path.resolve()}")
            print(f"Tables ({len(tables)}): {', '.join(tables)}\n")

        for table in tables:
            print(f"== {table} ==")
            try:
                rows = query_table(conn, table, limit=args.limit)
            except sqlite3.Error as exc:
                print(f"  Error fetching rows: {exc}")
                print()
                continue
            if not rows:
                print("  (no rows)\n")
                continue
            for row in rows:
                pretty = json.dumps(row, ensure_ascii=False, indent=2)
                print(pretty)
                print()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
