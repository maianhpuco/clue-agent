# react_split_pipeline.py
"""
Builds a LangGraph pipeline that iterates:
1) Plan PubMed queries with an LLM
2) Search PubMed via a tool
3) Summarize abstracts with the LLM
4) Extract ontology candidates with the LLM
5) Merge candidates into an ontology store
6) Persist iteration artifacts
7) Decide to stop or mutate queries and loop

Stops when either:
merged concept count ≥ min_concepts, or
iteration ≥ max_iters 

raph nodes (state is a dict)
bump: increment iteration
plan_queries: LLM → 2–4 queries (fallback seeds on iter 0)
search: call search_pubmed tool per query; tag origin
summarize_hits: LLM → strict JSON summaries per hit
extract_terms: LLM → candidate concepts (small JSON objects)
merge_concepts: merge by name_snake into state["ontology"]["concepts"]
persist_iteration: write queries/results/summaries/candidates and ontology delta
observe: compute stop condition
mutate_queries: LLM → 2–4 new queries (fallback if empty) 

"""
from __future__ import annotations
import os, time, json, argparse
from typing import Dict, Any, List
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# ---- bring in your existing tool exactly as-is ----
# from your_module import search_pubmed   # if it's in another file
# (for clarity, I inline a minimal signature here)
from langchain_core.tools import tool
import httpx
from lxml import etree

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_MIN_DELAY_S = float(os.getenv("NCBI_MIN_DELAY_S", "0.34"))
NCBI_MAX_RETRIES = int(os.getenv("NCBI_MAX_RETRIES", "3"))

def _ncbi_headers() -> Dict[str, str]:
    email = os.getenv("NCBI_EMAIL", "")
    headers = {"User-Agent": "tools-agent/0.1"}
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

@tool("search_pubmed")
def search_pubmed(query: str, k: int = 5) -> List[Dict[str, str]]:
    """Search PubMed for a query and return up to k hits with title/snippet/url."""
    results: List[Dict[str, str]] = []
    with httpx.Client(timeout=30) as client:
        es = _http_get(client, f"{NCBI_BASE}/esearch.fcgi",
                       {"db": "pubmed", "term": query, "retmode": "json", "retmax": str(k)})
        ids = [str(x) for x in es.json().get("esearchresult", {}).get("idlist", [])]
        if not ids:
            return []
        # batch efetch
        for i in range(0, len(ids), 4):
            batch = ids[i:i+4]
            ef = _http_get(client, f"{NCBI_BASE}/efetch.fcgi",
                           {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"})
            root = etree.fromstring(ef.content)
            for article in root.findall(".//PubmedArticle"):
                title_el = article.find(".//ArticleTitle")
                title = (title_el.text or "").strip() if title_el is not None else ""
                paras: List[str] = []
                for abs_el in article.findall(".//Abstract/AbstractText"):
                    text = (abs_el.text or "").strip()
                    if text:
                        paras.append(text)
                snippet = " ".join(paras)[:900]
                pmid_el = article.find(".//PMID")
                pmid = pmid_el.text if pmid_el is not None else ""
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
                if title or snippet:
                    results.append({"title": title, "snippet": snippet, "url": url})
    return results[:k]

# ------------------ Prompts (tiny & strict JSON) ------------------

PLAN_PROMPT = """\
You are a pathology planner.
Task: propose 2–4 concise PubMed queries to describe the class "{klass}" and its benign mimics.
Mix low-power architecture terms and high-power cytology terms.

Given previously tried queries:
{tried}

Return ONLY a JSON list of strings, e.g. ["q1", "q2"].
"""

SUMMARY_PROMPT = """\
Summarize this abstract snippet into a clinical morphology summary (≤60 words) and key tokens.

Return STRICT JSON:
{{
  "summary": "<≤60 words>",
  "low_power_terms": ["..."],
  "high_power_terms": ["..."],
  "caveats": ["..."]
}}
SNIPPET:
{snippet}
"""

EXTRACT_PROMPT = """\
Extract ontology concept candidates for class "{klass}" from the SNIPPET and SUMMARY.

Return STRICT JSON list of objects:
[
  {{"name_snake": "<snake_case>", "mags": ["5x","10x","20x"], "text": "<≤25 words>",
    "applies_to": ["{klass}"], "evidence": {{"title":"<t>", "url":"<u>"}} }},
  ...
]
SNIPPET: {snippet}
SUMMARY: {summary}
"""

MUTATE_PROMPT = """\
We need more/better coverage. Propose 2–4 NEW queries unlike the tried ones:

Missing hints:
{hints}

Previously tried:
{tried}

Return ONLY a JSON list of strings.
"""

SYSTEM = "You are a concise, clinically-minded pathology assistant. Always return strict JSON when asked."

# ------------------ Simple helpers ------------------

def ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")

def save_json(outdir: Path, name: str, data: Any) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    p = outdir / f"{name}.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p

# ------------------ Graph state is a plain dict ------------------

def build_graph(llm: ChatOpenAI):
    g = StateGraph(dict)

    # ---------- NODES ----------
    def plan_queries(state: Dict[str, Any]):
        tried = "\n".join(f"- {q}" for q in state["tried_queries"][-10:]) or "(none)"
        prompt = PLAN_PROMPT.format(klass=state["class_name"], tried=tried)
        txt = llm.invoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)]).content.strip()
        try:
            qs = [q for q in json.loads(txt) if isinstance(q, str) and q.strip()]
        except Exception:
            qs = []
        if not qs and state["iteration"] == 0:
            # minimal fallback
            qs = [
                f"{state['class_name']} histology morphology features low power",
                f"{state['class_name']} cytology nucleoli mitoses high power",
                f"{state['class_name']} benign mimics differential diagnosis histology",
            ]
        state["current_queries"] = qs[:4]
        return state

    def search(state: Dict[str, Any]):
        hits_all = []
        for q in state["current_queries"]:
            state["tried_queries"].append(q)
            hits = search_pubmed.invoke({"query": q, "k": state["k"]})  # tool call
            for h in hits:
                h["_origin_query"] = q
                hits_all.append(h)
        state["results"] = hits_all
        return state

    def summarize_hits(state: Dict[str, Any]):
        summaries = []
        for h in state["results"]:
            prompt = SUMMARY_PROMPT.format(snippet=h.get("snippet","")[:1600])
            txt = llm.invoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)]).content.strip()
            try:
                j = json.loads(txt)
            except Exception:
                j = {"summary":"", "low_power_terms":[],"high_power_terms":[],"caveats":[]}
            j["_title"] = h.get("title","")
            j["_url"] = h.get("url","")
            j["_origin_query"] = h.get("_origin_query","")
            summaries.append(j)
        state["summaries"] = summaries
        return state

    def extract_terms(state: Dict[str, Any]):
        # produce small set of candidates per hit (kept simple)
        cands = []
        for s in state["summaries"]:
            prompt = EXTRACT_PROMPT.format(
                klass=state["class_name"],
                snippet="",  # keep short; or pass the original snippet if you prefer
                summary=s.get("summary","")
            )
            txt = llm.invoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)]).content.strip()
            try:
                items = json.loads(txt)
                for it in items:
                    it["_origin_url"] = s.get("_url","")
                    it["_origin_title"] = s.get("_title","")
                    cands.append(it)
            except Exception:
                continue
        state["candidates"] = cands
        return state

    def merge_concepts(state: Dict[str, Any]):
        # very simple merge: by name_snake; first-win text; union mags; collect evidence
        onto = state["ontology"]
        delta = []
        for c in state.get("candidates", []):
            name = (c.get("name_snake") or "").strip()
            text = (c.get("text") or "").strip()
            mags = c.get("mags") or []
            applies = c.get("applies_to") or [state["class_name"]]
            ev = {"title": c.get("_origin_title",""), "url": c.get("_origin_url","")}
            if not name or not text or not mags:
                continue
            slot = onto["concepts"].setdefault(name, {"mags": [], "text": text, "applies_to": list(set(applies)), "evidence": []})
            # update mags
            slot["mags"] = sorted(list(set(slot["mags"]) | set(mags)))
            # keep shorter text if different
            if text and len(text) < len(slot.get("text","")):
                slot["text"] = text
            # applies_to union
            slot["applies_to"] = sorted(list(set(slot.get("applies_to", [])) | set(applies)))
            # evidence add
            if ev["url"] or ev["title"]:
                slot["evidence"].append(ev)
            delta.append(name)
        state["delta_concepts"] = sorted(list(set(delta)))
        return state

    def persist_iteration(state: Dict[str, Any]):
        out = Path(state["outdir"])
        tag = f"iter{state['iteration']}_{time.strftime('%Y%m%d_%H%M%S')}"
        save_json(out, f"queries_{tag}", state["current_queries"])
        save_json(out, f"results_{tag}", state["results"])
        save_json(out, f"summaries_{tag}", state["summaries"])
        save_json(out, f"candidates_{tag}", state.get("candidates", []))
        # write only the delta for easy diffing
        delta_export = {n: state["ontology"]["concepts"][n] for n in state.get("delta_concepts", [])}
        save_json(out, f"ontology_delta_{tag}", delta_export)
        return state

    def observe(state: Dict[str, Any]):
        # SIMPLE stop rule: stop when we have merged at least N unique concepts for this class
        min_concepts = state["min_concepts"]
        total = len(state["ontology"]["concepts"])
        state["stop"] = (total >= min_concepts) or (state["iteration"] >= state["max_iters"])
        return state

    def mutate_queries(state: Dict[str, Any]):
        hints = "Too few concepts merged; emphasize magnification words and benign mimics."
        tried = "\n".join(f"- {q}" for q in state["tried_queries"][-12:]) or "(none)"
        prompt = MUTATE_PROMPT.format(hints=hints, tried=tried)
        txt = llm.invoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)]).content.strip()
        try:
            qs = [q for q in json.loads(txt) if isinstance(q, str) and q.strip()]
        except Exception:
            qs = []
        if not qs:
            qs = [
                f"{state['class_name']} subcapsular nests capsule sinus histology",
                f"{state['class_name']} nuclear atypia mitoses high power histology",
            ]
        state["current_queries"] = qs[:4]
        return state

    def bump_iter(state: Dict[str, Any]):
        state["iteration"] += 1
        return state

    # ---------- GRAPH WIRING ----------
    g.add_node("bump", bump_iter)
    g.add_node("plan_queries", plan_queries)
    g.add_node("search", search)
    g.add_node("summarize_hits", summarize_hits)
    g.add_node("extract_terms", extract_terms)
    g.add_node("merge_concepts", merge_concepts)
    g.add_node("persist_iteration", persist_iteration)
    g.add_node("observe", observe)
    g.add_node("mutate_queries", mutate_queries)

    g.set_entry_point("bump")
    g.add_edge("bump", "plan_queries")
    g.add_edge("plan_queries", "search")
    g.add_edge("search", "summarize_hits")
    g.add_edge("summarize_hits", "extract_terms")
    g.add_edge("extract_terms", "merge_concepts")
    g.add_edge("merge_concepts", "persist_iteration")
    g.add_edge("persist_iteration", "observe")

    def decide(state: Dict[str, Any]) -> str:
        if state["stop"]:
            return "stop"
        return "continue"

    g.add_conditional_edges("observe", decide, {"continue": "mutate_queries", "stop": END})
    # loop back via bump to ensure iteration increases each cycle
    g.add_edge("mutate_queries", "bump")
    return g.compile()

# ------------------ CLI ------------------

if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser(description="Split ReAct pipeline (plan→search→summarize→extract→merge→observe)")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument("--outdir", default="runs/react_split")
    parser.add_argument("--class_name", default="breast carcinoma lymph node metastasis")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--max_iters", type=int, default=3)
    parser.add_argument("--min_concepts", type=int, default=4, help="Stop after this many concepts merged")
    args = parser.parse_args()

    llm = ChatOpenAI(model=args.model, temperature=0.2)

    # Initial state
    state: Dict[str, Any] = {
        "class_name": args.class_name,
        "outdir": args.outdir,
        "k": args.k,
        "max_iters": args.max_iters,
        "min_concepts": args.min_concepts,
        "iteration": 0,
        "tried_queries": [],
        "current_queries": [],
        "results": [],
        "summaries": [],
        "candidates": [],
        "ontology": {"concepts": {}},  # grows over time
        "delta_concepts": [],
        "stop": False,
    }

    graph = build_graph(llm)
    # increase recursion limit to allow more internal steps safely
    final_state = graph.invoke(state, config={"recursion_limit": 100})

    # write final ontology
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"final_ontology_{ts()}.json").open("w", encoding="utf-8") as f:
        json.dump(final_state["ontology"], f, ensure_ascii=False, indent=2)

    print(f"[DONE] iter={final_state['iteration']} stop={final_state['stop']} concepts={len(final_state['ontology']['concepts'])}")
    print(f"Saved final ontology to { (out / f'final_ontology_{ts()}.json').resolve() }")
