"""Ontology extraction utilities and MCP prompt builder."""

from __future__ import annotations

import json
import textwrap
from typing import Any, Dict, List, Optional, Tuple

from .db import get_search, insert_extraction, list_results, list_searches
from .settings import DATASET

ONT_KEY_FIELDS = [
    "name",
    "definition",
    "synonyms",
    "concept_type",
    "positives",
    "negatives",
    "magnifications",
]


def _select_search(keyword: str, source: Optional[str], search_id: Optional[int]) -> Tuple[int, Dict[str, Any]]:
    if search_id is not None:
        search = get_search(search_id)
        if not search:
            raise ValueError(f"Search id {search_id} not found.")
        if search["keyword"] != keyword:
            raise ValueError(f"Search id {search_id} keyword mismatch (expected '{keyword}', found '{search['keyword']}').")
        if source and search["source"] != source:
            raise ValueError(
                f"Search id {search_id} source mismatch (expected '{source}', found '{search['source']}')."
            )
        return search_id, search

    searches = list_searches(keyword, source)
    if not searches:
        raise ValueError(f"No cached searches for keyword '{keyword}' (source={source or 'any'}).")
    search = searches[0]
    return search["id"], search


def _prepare_context(results: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    context = []
    for idx, item in enumerate(results[:limit], start=1):
        context.append(
            {
                "index": idx,
                "title": item.get("title") or "",
                "snippet": item.get("snippet") or "",
                "url": item.get("url") or "",
                "published": item.get("published") or "",
                "license": item.get("license") or "",
            }
        )
    return context


def _summarise_context(context: List[Dict[str, Any]]) -> str:
    blocks = []
    for entry in context:
        title = entry["title"] or "Untitled"
        snippet = entry["snippet"].strip()
        url = entry["url"]
        blocks.append(
            textwrap.dedent(
                f"""\
                [{entry['index']}] {title}
                URL: {url}
                Summary: {snippet or 'N/A'}"""
            ).strip()
        )
    return "\n\n".join(blocks)


def _build_prompt(keyword: str, source: str, context: List[Dict[str, Any]]) -> str:
    context_block = _summarise_context(context)
    field_instructions = textwrap.dedent(
        """
        Required JSON fields:
        - name: concise label for the histopathology concept.
        - definition: single sentence, morphology-forward, emphasising diagnostic cues.
        - synonyms: list of lowercase or natural-case synonyms, deduplicated.
        - concept_type: one of ["class","compartment","morphology","interface","substructure"].
        - positives: 3–6 short phrases listing hallmark microscopic findings (patch scale).
        - negatives: 3–6 confounders or exclusions to avoid false positives.
        - magnifications: list subset of ["10x","20x","40x"] highlighting optimal recognition power.
        """
    ).strip()
    return textwrap.dedent(
        f"""
        You are curating the {DATASET} histopathology ontology.
        Keyword: "{keyword}"
        Source: {source}

        Use the search evidence below to draft a JSON object with the required fields.
        Focus on morphology cues and differential diagnosis guidance. When evidence is missing, leave the field as an empty list or descriptive placeholder.

        Evidence:
        {context_block}

        {field_instructions}

        Respond with valid JSON only.
        """
    ).strip()


def run_extraction(
    keyword: str,
    source: Optional[str],
    search_id: Optional[int],
    max_context: int,
    extractor: str,
    extraction_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resolved_search_id, search_meta = _select_search(keyword, source, search_id)
    results = list(list_results(resolved_search_id))
    if not results:
        raise ValueError(f"No cached results for search id {resolved_search_id}. Run the search tool first.")
    context = _prepare_context(results, max_context)
    prompt = _build_prompt(keyword, search_meta["source"], context)
    summary = _summarise_context(context)
    extraction_content: Dict[str, Any] = {
        "keyword": keyword,
        "source": search_meta["source"],
        "tool_name": search_meta["tool_name"],
        "search_id": resolved_search_id,
        "prompt": prompt,
        "summary": summary,
        "context": context,
        "extraction": extraction_payload
        if extraction_payload is not None
        else {field: [] if field.endswith("s") else "" for field in ONT_KEY_FIELDS},
    }
    extraction_id = insert_extraction(resolved_search_id, extractor, keyword, extraction_content)
    return {
        "status": "ok",
        "keyword": keyword,
        "source": search_meta["source"],
        "search_id": resolved_search_id,
        "extraction_id": extraction_id,
        "extractor": extractor,
        "prompt": prompt,
        "summary": summary,
        "context": context,
        "extraction": extraction_content["extraction"],
    }


__all__ = ["run_extraction", "ONT_KEY_FIELDS"]
