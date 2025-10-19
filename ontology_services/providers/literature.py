"""Literature provider implementations."""

from __future__ import annotations

import os
import textwrap
from typing import Dict, List, Literal

from ..http_client import http_get, strip_html
from .base import ProviderFunc, mock_result

LiteratureSource = Literal[
    "europe_pmc",
    "pubmed",
    "semantic_scholar",
    "crossref",
    "dimensions",
    "scopus",
    "web_of_science",
]


def search_europe_pmc(query: str, max_results: int) -> List[Dict[str, str]]:
    data = http_get(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        params={"query": query, "format": "json", "pageSize": max_results},
    )
    items = (data.get("resultList") or {}).get("result", []) if isinstance(data, dict) else []
    results: List[Dict[str, str]] = []
    for entry in items[:max_results]:
        title = entry.get("title") or ""
        pmcid = entry.get("pmcid")
        pmid = entry.get("pmid")
        if pmcid:
            url_item = f"https://europepmc.org/article/PMC/{pmcid}"
        elif pmid:
            url_item = f"https://europepmc.org/abstract/MED/{pmid}"
        else:
            url_item = entry.get("url") or ""
        snippet = entry.get("abstractText") or title
        results.append(
            {
                "title": title,
                "url": url_item,
                "published": str(entry.get("firstPublicationDate") or entry.get("pubYear") or ""),
                "license": entry.get("license") or "",
                "snippet": textwrap.shorten(snippet, width=800, placeholder="..."),
                "source": "europe_pmc",
            }
        )
    return results


def search_pubmed(query: str, max_results: int) -> List[Dict[str, str]]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    search_data = http_get(
        f"{base}/esearch.fcgi",
        params={"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"},
    )
    idlist = (
        (search_data.get("esearchresult") or {}).get("idlist", [])[:max_results]
        if isinstance(search_data, dict)
        else []
    )
    if not idlist:
        return []

    summary_data = http_get(
        f"{base}/esummary.fcgi",
        params={"db": "pubmed", "id": ",".join(idlist), "retmode": "json"},
    )
    result_payload = summary_data.get("result") if isinstance(summary_data, dict) else {}
    uids = result_payload.get("uids", []) if isinstance(result_payload, dict) else []

    records: List[Dict[str, str]] = []
    for uid in uids:
        record = result_payload.get(uid, {}) if isinstance(result_payload, dict) else {}
        if not record:
            continue
        title = record.get("title") or ""
        snippet = record.get("elocationid") or record.get("source") or title
        records.append(
            {
                "title": title,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                "published": record.get("pubdate") or record.get("epubdate") or "",
                "license": "",
                "snippet": textwrap.shorten(snippet or title, width=800, placeholder="..."),
                "source": "pubmed",
            }
        )
    return records


def search_semantic_scholar(query: str, max_results: int) -> List[Dict[str, str]]:
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,abstract,year,url,openAccessPdf",
    }
    headers: Dict[str, str] = {}
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    data = http_get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params=params,
        headers=headers,
    )
    items = data.get("data", []) if isinstance(data, dict) else []
    results: List[Dict[str, str]] = []
    for entry in items[:max_results]:
        title = entry.get("title") or ""
        open_access = entry.get("openAccessPdf") or {}
        url_item = open_access.get("url") or entry.get("url") or ""
        abstract_text = entry.get("abstract") or title
        results.append(
            {
                "title": title,
                "url": url_item,
                "published": str(entry.get("year") or ""),
                "license": "",
                "snippet": textwrap.shorten(abstract_text, width=800, placeholder="..."),
                "source": "semantic_scholar",
            }
        )
    return results


def search_crossref(query: str, max_results: int) -> List[Dict[str, str]]:
    data = http_get(
        "https://api.crossref.org/works",
        params={"query": query, "rows": max_results},
    )
    message = data.get("message", {}) if isinstance(data, dict) else {}
    items = message.get("items", []) if isinstance(message, dict) else []
    results: List[Dict[str, str]] = []
    for entry in items[:max_results]:
        title_list = entry.get("title") or []
        title = title_list[0] if title_list else ""
        date_parts = (entry.get("issued") or {}).get("date-parts", [])
        published = ""
        if date_parts and date_parts[0]:
            published = "-".join(str(part) for part in date_parts[0])
        license_entries = entry.get("license") or []
        license_url = license_entries[0].get("URL", "") if license_entries else ""
        abstract = strip_html(entry.get("abstract") or "")
        snippet_source = abstract or title
        results.append(
            {
                "title": title,
                "url": entry.get("URL") or "",
                "published": published,
                "license": license_url,
                "snippet": textwrap.shorten(snippet_source, width=800, placeholder="..."),
                "source": "crossref",
            }
        )
    return results


def search_dimensions(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"Dimensions analytic overview for {query}",
            "https://app.dimensions.ai/",
            "2023-08-10",
            "Subscription",
            f"Dimensions analytics summary describing grants, publications, and patents involving {query}.",
        )
    ][:max_results]


def search_scopus(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"Scopus indexed record for {query}",
            "https://www.scopus.com/",
            "2018-03-12",
            "Subscription",
            f"Scopus abstracted information including author affiliations and citation metrics for {query}.",
        )
    ][:max_results]


def search_web_of_science(query: str, max_results: int) -> List[Dict[str, str]]:
    return [
        mock_result(
            f"Web of Science core collection hit for {query}",
            "https://www.webofscience.com/",
            "2017-02-18",
            "Subscription",
            f"Web of Science indexing record noting subject categories and cited references tied to {query}.",
        )
    ][:max_results]


LITERATURE_PROVIDERS: Dict[str, ProviderFunc] = {
    "europe_pmc": search_europe_pmc,
    "pubmed": search_pubmed,
    "semantic_scholar": search_semantic_scholar,
    "crossref": search_crossref,
    "dimensions": search_dimensions,
    "scopus": search_scopus,
    "web_of_science": search_web_of_science,
}

__all__ = ["LiteratureSource", "LITERATURE_PROVIDERS"]
