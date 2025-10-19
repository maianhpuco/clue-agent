#!/usr/bin/env python3
"""
MCP Server: Ontology Knowledge Search (stdio)
- search_literature: query literature indices (Europe PMC, PubMed, Semantic Scholar, etc.) and persist hits
- search_pathology_reference: pull high-yield pathology reference snippets to cache locally
- search_terminology: query ontology services for definitions, synonyms, and relationships
- fetch_results: retrieve stored hits for a keyword (optionally filtered by source)
"""

from __future__ import annotations

import json
from typing import Optional

try:
    from fastmcp import FastMCP
except ImportError as exc:
    raise SystemExit("fastmcp is not installed. Run: pip install fastmcp") from exc

from ontology_services.extraction import run_extraction
from ontology_services.ontology_builder import build_and_save_tree
from ontology_services.providers import (
    LITERATURE_PROVIDERS,
    ONTOLOGY_PROVIDERS,
    PATHOLOGY_PROVIDERS,
    LiteratureSource,
    OntologySource,
    PathologySource,
)
from ontology_services.search import execute_search
from ontology_services.storage import read_results, read_search

mcp = FastMCP("ontology_knowledge")


@mcp.tool()
def search_literature(
    keyword: str,
    source: LiteratureSource = "europe_pmc",
    max_results: int = 5,
) -> str:
    """Query a literature source and persist results for later retrieval."""
    return execute_search(keyword, source, "search_literature", max_results, LITERATURE_PROVIDERS)


@mcp.tool()
def search_pathology_reference(
    keyword: str,
    source: PathologySource = "pathology_outlines",
    max_results: int = 5,
) -> str:
    """Retrieve curated surgical pathology references summarizing diagnostic cues."""
    return execute_search(keyword, source, "search_pathology_reference", max_results, PATHOLOGY_PROVIDERS)


@mcp.tool()
def search_terminology(
    keyword: str,
    source: OntologySource = "ncbo_bioportal",
    max_results: int = 5,
) -> str:
    """Lookup ontology and terminology sources for synonyms and hierarchical relations."""
    return execute_search(keyword, source, "search_terminology", max_results, ONTOLOGY_PROVIDERS)


@mcp.tool()
def fetch_results(keyword: str, source: Optional[str] = None) -> str:
    """Retrieve cached search results for a keyword."""
    keyword = keyword.strip()
    if not keyword:
        return json.dumps({"status": "error", "error": "Keyword must not be empty."}, indent=2)

    payload = read_results(keyword, source)
    if not payload["sources"]:
        return json.dumps(
            {"status": "not_found", "keyword": keyword, "source": source, "message": "No cached results."},
            indent=2,
        )
    payload["available_sources"] = sorted(payload["sources"])
    return json.dumps({"status": "ok", "data": payload}, indent=2, ensure_ascii=False)


@mcp.tool()
def query_cache(
    search_id: Optional[int] = None,
    keyword: Optional[str] = None,
    source: Optional[str] = None,
    include_results: bool = True,
    include_extractions: bool = True,
) -> str:
    """Query cached searches or extractions using flexible filters."""
    if search_id is not None:
        bundle = read_search(search_id, include_results=include_results, include_extractions=include_extractions)
        if not bundle:
            return json.dumps({"status": "not_found", "search_id": search_id}, indent=2)
        return json.dumps({"status": "ok", "data": bundle}, indent=2, ensure_ascii=False)

    if keyword:
        payload = read_results(keyword.strip(), source)
        if not payload["sources"]:
            return json.dumps({"status": "not_found", "keyword": keyword, "source": source}, indent=2)
        for src, entry in payload["sources"].items():
            for search in entry.get("searches", []):
                if not include_results:
                    search.pop("results", None)
                if not include_extractions:
                    search.pop("extractions", None)
        payload["available_sources"] = sorted(payload["sources"])
        return json.dumps({"status": "ok", "data": payload}, indent=2, ensure_ascii=False)

    return json.dumps({"status": "error", "error": "Provide either search_id or keyword."}, indent=2)


@mcp.tool()
def ontology_extract(
    keyword: str,
    source: Optional[str] = None,
    search_id: Optional[int] = None,
    max_context: int = 5,
    extractor: str = "ontology_extract",
    extraction: Optional[str] = None,
) -> str:
    """
    Build an ontology-focused prompt and summary from cached search results, optionally persisting structured output.
    """
    keyword = keyword.strip()
    if not keyword:
        return json.dumps({"status": "error", "error": "Keyword must not be empty."}, indent=2)
    extraction_payload = None
    if extraction:
        try:
            extraction_payload = json.loads(extraction)
        except json.JSONDecodeError as exc:
            return json.dumps({"status": "error", "error": f"Invalid extraction JSON: {exc}"}, indent=2)
    try:
        result = run_extraction(
            keyword=keyword,
            source=source,
            search_id=search_id,
            max_context=max_context,
            extractor=extractor,
            extraction_payload=extraction_payload,
        )
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)}, indent=2)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def build_ontology_tree(include_base: bool = True, version_name: Optional[str] = None) -> str:
    """Rebuild the ontology tree and persist a versioned JSON snapshot."""
    try:
        result = build_and_save_tree(include_base=include_base, version_name=version_name)
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)}, indent=2)
    return json.dumps(result, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
