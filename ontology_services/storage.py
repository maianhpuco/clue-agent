"""Persistence helpers for caching provider search results in SQLite."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .db import (
    bulk_insert_results,
    get_search,
    insert_search,
    list_extractions,
    list_results,
    list_searches,
)


def write_results(
    keyword: str,
    source: str,
    tool_name: str,
    max_results: int,
    results: List[Dict[str, Any]],
) -> Tuple[int, int, int]:
    args = {"keyword": keyword, "source": source, "tool": tool_name, "max_results": max_results}
    search_id = insert_search(keyword, source, tool_name, max_results, args)
    added = bulk_insert_results(search_id, results)
    total_cached = len(list_results(search_id))
    return search_id, added, total_cached


def read_results(keyword: str, source: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"keyword": keyword, "sources": {}}
    searches = list_searches(keyword, source)
    for search in searches:
        src = search["source"]
        entry = payload["sources"].setdefault(src, {"searches": []})
        search_id = search["id"]
        entry["searches"].append(
            {
                "search_id": search_id,
                "tool_name": search["tool_name"],
                "requested_at": search["requested_at"],
                "max_results": search["max_results"],
                "args": search["args"],
                "results": list(list_results(search_id)),
                "extractions": list(list_extractions(search_id=search_id)),
            }
        )
    return payload


def read_search(
    search_id: int,
    include_results: bool = True,
    include_extractions: bool = True,
) -> Optional[Dict[str, Any]]:
    search = get_search(search_id)
    if not search:
        return None
    bundle: Dict[str, Any] = {
        "search_id": search_id,
        "keyword": search["keyword"],
        "source": search["source"],
        "tool_name": search["tool_name"],
        "requested_at": search["requested_at"],
        "max_results": search["max_results"],
        "args": search["args"],
    }
    if include_results:
        bundle["results"] = list(list_results(search_id))
    if include_extractions:
        bundle["extractions"] = list(list_extractions(search_id=search_id))
    return bundle


__all__ = ["write_results", "read_results", "read_search"]
