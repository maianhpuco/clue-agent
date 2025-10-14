from __future__ import annotations
import os, time, json
from typing import Dict, Any, List

import httpx
from lxml import etree
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
import argparse
from pathlib import Path

# ------------------
# PubMed helper (single-query, polite)
# ------------------
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
		es = _http_get(client, f"{NCBI_BASE}/esearch.fcgi", {"db": "pubmed", "term": query, "retmode": "json", "retmax": str(k)})
		ids = [str(x) for x in es.json().get("esearchresult", {}).get("idlist", [])]
		if not ids:
			return []
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
					results.append({"title": title, "snippet": snippet, "url": url})
	return results[:k]


# ------------------
# Agent and State
# ------------------
AgentState = Dict[str, Any]

class Agent:
	def __init__(self, model: ChatOpenAI, tools: List[Any], system: str = ""):
		self.system = system
		self.tools = {t.name: t for t in tools}
		self.model = model.bind_tools(tools)
		graph = StateGraph(AgentState)
		graph.add_node("llm", self.call_openai)
		graph.add_node("action", self.take_action)
		graph.add_conditional_edges("llm", self.exists_action, {True: "action", False: END})
		graph.add_edge("action", "llm")
		graph.set_entry_point("llm")
		self.graph = graph.compile()

	def exists_action(self, state: AgentState):
		result: AIMessage = state['messages'][-1]
		return bool(getattr(result, 'tool_calls', []) and len(result.tool_calls) > 0)

	def call_openai(self, state: AgentState):
		messages = state['messages']
		if self.system:
			messages = [SystemMessage(content=self.system)] + messages
		message: AIMessage = self.model.invoke(messages)
		# Append AI response to conversation
		return {'messages': state['messages'] + [message]}

	def take_action(self, state: AgentState):
		ai_msg: AIMessage = state['messages'][-1]
		tool_calls = getattr(ai_msg, 'tool_calls', []) or []
		results: List[ToolMessage] = []
		for t in tool_calls:
			name = t.get('name') if isinstance(t, dict) else t.name
			args = t.get('args') if isinstance(t, dict) else t.args
			call_id = t.get('id') if isinstance(t, dict) else t.id
			if name not in self.tools:
				result = "bad tool name, retry"
			else:
				try:
					result = self.tools[name].invoke(args)
				except Exception as e:
					result = f"tool error: {e}"
			results.append(ToolMessage(tool_call_id=call_id, name=name, content=json.dumps(result, ensure_ascii=False)))
		# Append tool results to conversation
		return {'messages': state['messages'] + results}


def _serialize_message(msg: Any) -> Dict[str, Any]:
	role = "assistant"
	if isinstance(msg, HumanMessage):
		role = "user"
	elif isinstance(msg, SystemMessage):
		role = "system"
	elif isinstance(msg, ToolMessage):
		role = "tool"
	content = getattr(msg, 'content', '')
	tool_calls = getattr(msg, 'tool_calls', None)
	name = getattr(msg, 'name', None)
	tool_call_id = getattr(msg, 'tool_call_id', None)
	return {"role": role, "content": content, "tool_calls": tool_calls, "name": name, "tool_call_id": tool_call_id}


# ------------------
# CLI runner
# ------------------
if __name__ == "__main__":
	load_dotenv()
	parser = argparse.ArgumentParser(description="Tools-based pathology agent demo")
	parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
	parser.add_argument("--outdir", default="runs/tools_demo")
	parser.add_argument("--prompt", default=(
		"Label: breast carcinoma metastasis in sentinel lymph node.\n"
		"Goal: propose search plan, then call search_pubmed for key phrases."
	))
	args = parser.parse_args()

	llm = ChatOpenAI(model=args.model, temperature=0.2)
	agent = Agent(model=llm, tools=[search_pubmed], system=(
		"You are a pathology agent. Decide sources/keywords and call tools as needed."
	))
	state: AgentState = {"messages": [HumanMessage(content=args.prompt)]}
	final = agent.graph.invoke(state)

	outdir = Path(args.outdir)
	outdir.mkdir(parents=True, exist_ok=True)
	stamp = int(time.time())
	# Save full conversation as JSONL
	with (outdir / f"conversation_{stamp}.jsonl").open("w", encoding="utf-8") as f:
		for m in final["messages"]:
			f.write(json.dumps(_serialize_message(m), ensure_ascii=False) + "\n")
	print(f"Saved conversation to {(outdir / f'conversation_{stamp}.jsonl').resolve()}")
