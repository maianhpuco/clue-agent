"""Shared search execution utilities for MCP tools."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .providers.base import ProviderFunc
from .storage import write_results


def run_provider(providers: Dict[str, ProviderFunc], source: str, query: str, max_results: int) -> List[Dict[str, Any]]:
    if source not in providers:
        available = ", ".join(sorted(providers))
        raise ValueError(f"Unsupported source '{source}'. Available sources: {available}")
    return providers[source](query, max_results)


def execute_search(
    keyword: str,
    source: str,
    tool_name: str,
    max_results: int,
    providers: Dict[str, ProviderFunc],
) -> str:
    keyword = keyword.strip()
    if not keyword:
        return json.dumps({"status": "error", "error": "Keyword must not be empty."}, indent=2)
    try:
        results = run_provider(providers, source, keyword, max_results)
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)}, indent=2)

    search_id, added, total_cached = write_results(keyword, source, tool_name, max_results, results)
    summary = {
        "status": "ok",
        "keyword": keyword,
        "source": source,
        "tool_name": tool_name,
        "search_id": search_id,
        "results_returned": len(results),
        "results_stored": added,
        "total_cached": total_cached,
        "preview": results[: min(3, len(results))],
    }
    return json.dumps(summary, indent=2, ensure_ascii=False)


__all__ = ["run_provider", "execute_search"]
