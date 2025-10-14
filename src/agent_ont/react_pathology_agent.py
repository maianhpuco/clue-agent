#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangGraph ReAct Pathology Agent (simplified):
- Input: dataset key and a short label description (e.g., Camelyon16 tumor vs normal)
- Loop (single pass for now):
  1) Think: decide where to search (sources) and generate ~10 keywords
  2) Act: search PubMed with those keywords
  3) Observe: draft candidate concepts (concise, no duplicates)
  4) Persist: save thoughts, keywords, and search results to outdir

Usage:
  python -m src.agent_ont.react_pathology_agent --dataset camelyon16 --label_desc "breast carcinoma metastasis in sentinel lymph node" --outdir runs/c16_simple --k 5
"""
from __future__ import annotations
import argparse, json, os, time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any

import httpx
from lxml import etree
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

try:
	from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
	OpenAI = None  # type: ignore

# =========================
# INPUTS
# =========================

@dataclass
class SimpleAdapter:
	key: str
	default_sources: List[str]

ADAPTERS: Dict[str, SimpleAdapter] = {
	"camelyon16": SimpleAdapter(key="camelyon16", default_sources=["pubmed", "wikipedia"]),
	"tcga_lung": SimpleAdapter(key="tcga_lung", default_sources=["pubmed", "wikipedia"]),
	"tcga_renal": SimpleAdapter(key="tcga_renal", default_sources=["pubmed", "wikipedia"]),
}

# =========================
# LLM PROMPTS
# =========================

SYSTEM_PROMPT = """
You are a pathology ReAct agent. You think briefly, choose sources, propose search keywords, observe results, and draft concise candidate concepts.
"""

THINK_SOURCES_PROMPT = """
Task: Decide where to search for knowledge about this label.
Label description: {label_desc}
Dataset hint: {dataset}
Return a JSON list of sources in priority order (strings), choosing among ["pubmed","wikipedia"].
"""

THINK_KEYWORDS_PROMPT = """
Task: Propose about 10 short search keywords/phrases for the label.
Label description: {label_desc}
Return a strict JSON list of ~10 strings. Keep concise and morphology-focused.
"""

OBSERVE_DRAFT_PROMPT = """
Task: Draft concise candidate concept(s) from these snippets. Avoid duplicates.
Return a JSON list of strings (each 3–10 words).
SNIPPETS:
{snippets}
"""

# =========================
# SEARCH BACKEND (PubMed) with rate limiting
# =========================

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_MIN_DELAY_S = float(os.getenv("NCBI_MIN_DELAY_S", "0.34"))
NCBI_MAX_RETRIES = int(os.getenv("NCBI_MAX_RETRIES", "3"))


def _ncbi_headers() -> Dict[str, str]:
	email = os.getenv("NCBI_EMAIL", "")
	ua = "clue-agent-ont/0.1 (+https://example.invalid)"
	headers = {"User-Agent": ua}
	if email:
		headers["From"] = email
	api_key = os.getenv("NCBI_API_KEY")
	if api_key:
		headers["api-key"] = api_key
	return headers


def _http_get(client: httpx.Client, url: str, params: Dict[str, str]) -> httpx.Response:
	retry = 0
	while True:
		resp = client.get(url, params=params, headers=_ncbi_headers())
		if resp.status_code == 429 or resp.status_code >= 500:
			retry += 1
			time.sleep(NCBI_MIN_DELAY_S * (2 ** (retry - 1)))
			if retry <= NCBI_MAX_RETRIES:
				continue
		resp.raise_for_status()
		time.sleep(NCBI_MIN_DELAY_S)
		return resp


def pubmed_search_once(keywords: List[str], k: int) -> List[Dict[str, str]]:
	results: List[Dict[str, str]] = []
	with httpx.Client(timeout=30) as client:
		for q in keywords:
			es = _http_get(client, f"{NCBI_BASE}/esearch.fcgi", {"db": "pubmed", "term": q, "retmode": "json", "retmax": str(k)})
			ids = [str(x) for x in es.json().get("esearchresult", {}).get("idlist", [])]
			if not ids:
				continue
			for i in range(0, len(ids), 3):
				batch = ids[i:i+3]
				ef = _http_get(client, f"{NCBI_BASE}/efetch.fcgi", {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"})
				root = etree.fromstring(ef.content)
				for article in root.findall(".//PubmedArticle"):
					title_el = article.find(".//ArticleTitle")
					title = (title_el.text or "").strip() if title_el is not None else ""
					paras: List[str] = []
					for abs_el in article.findall(".//Abstract/AbstractText"):
						text = (abs_el.text or "").strip()
						if text:
							paras.append(text)
					snippet = " ".join(paras)[:800]
					pmid_el = article.find(".//PMID")
					pmid = pmid_el.text if pmid_el is not None else ""
					url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
					if title or snippet:
						results.append({"title": title, "snippet": snippet, "url": url, "_origin_query": q})
	return results

# =========================
# LLM CALL
# =========================

def call_llm(system_prompt: str, user_prompt: str, model: str) -> str:
	load_dotenv()
	api_key = os.getenv("OPENAI_API_KEY")
	base_url = os.getenv("OPENAI_BASE_URL")
	if not api_key or OpenAI is None:
		print("No API key or client found, using fallback heuristics")
		# Fallback lightweight heuristics if no API key or client
		if "sources in priority order" in user_prompt:
			return json.dumps(["pubmed", "wikipedia"])
		if "Propose about 10 short search" in user_prompt:
			return json.dumps([
				"subcapsular sinus metastasis breast carcinoma lymph node",
				"cohesive epithelial nests capsule breach low-power histology",
				"nuclear atypia mitotic figures 20x histology",
				"germinal center tingible macrophages histology mimic",
				"sinus histiocytes foamy macrophages mimic",
				"endothelial lining lymphatic vs epithelial nests",
				"lymphovascular emboli lymph node metastasis",
				"capsule hilum adipose lymph node architecture",
				"necrosis tumor nests lymph node",
				"reactive lymphoid follicles vs metastasis",
			])
		if "Draft concise candidate concept(s)" in user_prompt:
			return json.dumps([
				"subcapsular cohesive tumor nests at lymph node capsule",
				"nuclear atypia and mitotic figures at high power",
				"sinus histiocytes mimic tumor at low power",
			])
		return "[]"
	client = OpenAI(api_key=api_key, base_url=base_url)
	resp = client.chat.completions.create(
		model=model,
		messages=[
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": user_prompt},
		],
		temperature=0.2,
	)
	return resp.choices[0].message.content or ""

# =========================
# STATE AND NODES
# =========================

class SimpleState(BaseModel):
	dataset: str
	label_desc: str
	outdir: str
	k: int = 5
	model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
	sources: List[str] = Field(default_factory=list)
	keywords: List[str] = Field(default_factory=list)
	results: List[Dict[str, Any]] = Field(default_factory=list)
	concepts: List[str] = Field(default_factory=list)
	trace: List[Dict[str, Any]] = Field(default_factory=list)


def node_think_sources(state: SimpleState) -> SimpleState:
	adapter = ADAPTERS.get(state.dataset, SimpleAdapter(key=state.dataset, default_sources=["pubmed"]))
	prompt = THINK_SOURCES_PROMPT.format(label_desc=state.label_desc, dataset=adapter.key)
	raw = call_llm(SYSTEM_PROMPT, prompt, state.model)
	try:
		sources = json.loads(raw)
		sources = [s for s in sources if s in ["pubmed","wikipedia"]]
	except Exception:
		sources = adapter.default_sources
	state.sources = sources or adapter.default_sources
	state.trace.append({
		"step": "think_sources",
		"prompt": prompt,
		"raw": raw,
		"parsed": state.sources,
	})
	return state


def node_think_keywords(state: SimpleState) -> SimpleState:
	prompt = THINK_KEYWORDS_PROMPT.format(label_desc=state.label_desc)
	raw = call_llm(SYSTEM_PROMPT, prompt, state.model)
	try:
		kw = json.loads(raw)
		kw = [k for k in kw if isinstance(k, str) and k.strip()]
	except Exception:
		kw = []
	state.keywords = kw[:10]
	state.trace.append({
		"step": "think_keywords",
		"prompt": prompt,
		"raw": raw,
		"parsed": state.keywords,
	})
	return state


def node_search(state: SimpleState) -> SimpleState:
	if not state.keywords:
		state.results = []
		state.trace.append({"step": "search", "note": "no keywords; skipping"})
		return state
	if not state.sources or state.sources[0] == "pubmed":
		# Execute per-keyword to capture detailed trace
		results: List[Dict[str, Any]] = []
		with httpx.Client(timeout=30) as client:
			for q in state.keywords:
				# esearch
				es = _http_get(client, f"{NCBI_BASE}/esearch.fcgi", {"db": "pubmed", "term": q, "retmode": "json", "retmax": str(state.k)})
				es_json = es.json()
				ids = [str(x) for x in es_json.get("esearchresult", {}).get("idlist", [])]
				state.trace.append({
					"step": "search_esearch",
					"query": q,
					"pmids": ids,
				})
				if not ids:
					continue
				# efetch in small batches
				for i in range(0, len(ids), 3):
					batch = ids[i:i+3]
					ef = _http_get(client, f"{NCBI_BASE}/efetch.fcgi", {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"})
					root = etree.fromstring(ef.content)
					batch_results: List[Dict[str, Any]] = []
					for article in root.findall(".//PubmedArticle"):
						title_el = article.find(".//ArticleTitle")
						title = (title_el.text or "").strip() if title_el is not None else ""
						paras: List[str] = []
						for abs_el in article.findall(".//Abstract/AbstractText"):
							text = (abs_el.text or "").strip()
							if text:
								paras.append(text)
						snippet = " ".join(paras)[:800]
						pmid_el = article.find(".//PMID")
						pmid = pmid_el.text if pmid_el is not None else ""
						url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
						if title or snippet:
							item = {"title": title, "snippet": snippet, "url": url, "_origin_query": q}
							batch_results.append(item)
					results.extend(batch_results)
					state.trace.append({
						"step": "search_efetch",
						"query": q,
						"batch_pmids": batch,
						"hits": len(batch_results),
					})
		state.results = results
	return state


def node_observe_draft(state: SimpleState) -> SimpleState:
	snips = []
	for r in state.results[:10]:
		if r.get("title"):
			snips.append(r["title"])
		if r.get("snippet"):
			snips.append(r["snippet"])
	prompt = OBSERVE_DRAFT_PROMPT.format(snippets="\n".join(snips)[:2000])
	raw = call_llm(SYSTEM_PROMPT, prompt, state.model)
	try:
		concepts = json.loads(raw)
		concepts = [c for c in concepts if isinstance(c, str) and c.strip()]
	except Exception:
		concepts = []
	state.concepts = concepts
	state.trace.append({
		"step": "observe_draft",
		"prompt": prompt,
		"raw": raw,
		"parsed": state.concepts,
	})
	return state


def node_persist(state: SimpleState) -> SimpleState:
	out = Path(state.outdir)
	out.mkdir(parents=True, exist_ok=True)
	save = {
		"dataset": state.dataset,
		"label_desc": state.label_desc,
		"sources": state.sources,
		"keywords": state.keywords,
		"results": state.results,
		"concepts": state.concepts,
	}
	stamp = int(time.time())
	(out / f"first_loop_{stamp}.json").write_text(json.dumps(save, ensure_ascii=False, indent=2), encoding="utf-8")
	(out / f"trace_{stamp}.json").write_text(json.dumps(state.trace, ensure_ascii=False, indent=2), encoding="utf-8")
	return state

# =========================
# GRAPH
# =========================

def build_graph() -> StateGraph:
	g = StateGraph(SimpleState)
	g.add_node("think_sources", node_think_sources)
	g.add_node("think_keywords", node_think_keywords)
	g.add_node("search", node_search)
	g.add_node("observe_draft", node_observe_draft)
	g.add_node("persist", node_persist)
 
	g.set_entry_point("think_sources")
	g.add_edge("think_sources", "think_keywords")
	g.add_edge("think_keywords", "search")
	g.add_edge("search", "observe_draft")
	g.add_edge("observe_draft", "persist")
	return g

# =========================
# CLI
# =========================

def main():
	ap = argparse.ArgumentParser(description="Simplified LangGraph ReAct Pathology Agent (first loop)")
	ap.add_argument("--dataset", required=True, choices=list(ADAPTERS.keys()))
	ap.add_argument("--label_desc", required=True, help="Short label description (e.g., camelyon16 tumor class)")
	ap.add_argument("--outdir", required=True)
	ap.add_argument("--k", type=int, default=5)
	ap.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
	args = ap.parse_args()

	state = SimpleState(dataset=args.dataset, label_desc=args.label_desc, outdir=args.outdir, k=args.k, model=args.model)

	# Build raw graph and export visualization
	raw_graph = build_graph()
	outdir_path = Path(args.outdir)
	outdir_path.mkdir(parents=True, exist_ok=True)
	try:
		gvis = raw_graph.get_graph()
		# Mermaid export if available
		mermaid_fn = outdir_path / "graph.mmd"
		if hasattr(gvis, "draw_mermaid"):
			mmd = gvis.draw_mermaid()
			mermaid_fn.write_text(mmd, encoding="utf-8")
		# PNG export if backend available
		png_fn = outdir_path / "graph.png"
		if hasattr(gvis, "draw_png"):
			gvis.draw_png(str(png_fn))
	except Exception:
		pass

	graph = raw_graph.compile()
	final_state = graph.invoke(state)
	print("Sources:", final_state.get("sources"))
	print("Keywords:", final_state.get("keywords"))
	print("Concepts:", final_state.get("concepts"))
	print("Saved to:", outdir_path.resolve())
	if (outdir_path / "graph.mmd").exists():
		print("Graph (Mermaid):", (outdir_path / "graph.mmd").resolve())
	if (outdir_path / "graph.png").exists():
		print("Graph (PNG):", (outdir_path / "graph.png").resolve())


if __name__ == "__main__":
	main()
