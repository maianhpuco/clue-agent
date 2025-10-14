import os
from typing import List, Dict, Optional
import httpx
import backoff
from lxml import etree

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _headers() -> Dict[str, str]:
	"""Construct NIH-friendly headers including User-Agent and optional email."""
	email = os.getenv("NCBI_EMAIL", "")
	ua = "clue-agent/0.1 (+https://example.invalid)"
	headers = {"User-Agent": ua}
	if email:
		headers["From"] = email
	return headers


@backoff.on_exception(backoff.expo, (httpx.HTTPError,), max_time=30)
async def pubmed_esearch(query: str, retmax: int = 20) -> List[str]:
	"""Call ESearch to retrieve PubMed IDs for a query (JSON idlist)."""
	params = {
		"db": "pubmed",
		"term": query,
		"retmode": "json",
		"retmax": str(retmax),
	}
	async with httpx.AsyncClient(timeout=20) as client:
		resp = await client.get(f"{NCBI_BASE}/esearch.fcgi", params=params, headers=_headers())
		resp.raise_for_status()
		data = resp.json()
		ids = data.get("esearchresult", {}).get("idlist", [])
		return [str(i) for i in ids]


@backoff.on_exception(backoff.expo, (httpx.HTTPError,), max_time=30)
async def pubmed_efetch_abstracts(pmids: List[str]) -> Dict[str, str]:
	"""Call EFetch to retrieve abstracts for PMIDs and parse them from XML."""
	if not pmids:
		return {}
	params = {
		"db": "pubmed",
		"id": ",".join(pmids),
		"retmode": "xml",
	}
	async with httpx.AsyncClient(timeout=30) as client:
		resp = await client.get(f"{NCBI_BASE}/efetch.fcgi", params=params, headers=_headers())
		resp.raise_for_status()
		xml_root = etree.fromstring(resp.content)
		abstracts: Dict[str, str] = {}
		for article in xml_root.findall(".//PubmedArticle"):
			pmid_el = article.find(".//PMID")
			pmid = pmid_el.text if pmid_el is not None else None
			para_texts: List[str] = []
			for abs_el in article.findall(".//Abstract/AbstractText"):
				text = (abs_el.text or "").strip()
				if text:
					para_texts.append(text)
			if pmid and para_texts:
				abstracts[pmid] = "\n".join(para_texts)
		return abstracts
