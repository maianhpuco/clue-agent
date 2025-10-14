import asyncio
from typing import List
from langgraph.types import RunnableConfig
from langchain_openai import ChatOpenAI

from ..agent.pubmed import pubmed_esearch, pubmed_efetch_abstracts
from ..agent.spec import validate_concepts_json
from .state import AgentState


async def node_search(state: AgentState, config: RunnableConfig) -> AgentState:
	"""Search PubMed with user queries; collect a deduplicated, bounded PMID list."""
	pmids: List[str] = []
	for q in state.queries:
		ids = await pubmed_esearch(q, retmax=25)
		pmids.extend(ids)
	state.pmids = list(dict.fromkeys(pmids))[:60]
	return state


async def node_fetch(state: AgentState, config: RunnableConfig) -> AgentState:
	"""Fetch abstracts for discovered PMIDs (XML efetch -> parsed text)."""
	state.abstracts = await pubmed_efetch_abstracts(state.pmids)
	return state


async def node_synthesize(state: AgentState, config: RunnableConfig) -> AgentState:
	"""Ask the LLM to synthesize JSON given the system prompt and observations."""
	llm = ChatOpenAI(model=config.get("model", "gpt-4o-mini"), temperature=0.2)
	observations = []
	for pmid, text in state.abstracts.items():
		observations.append(f"PMID {pmid}:\n{text}")
	obs_text = "\n\n".join(observations[:20])
	q_text = "\n".join(f"- {q}" for q in state.queries)
	user_prompt = (
		"You can use the following observations from PubMed abstracts to construct the JSON list.\n"
		"Queries used:\n" + q_text + "\n\n"
		"Observations (subset):\n" + obs_text + "\n\n"
		"Return only JSON per the spec."
	)
	resp = await llm.ainvoke([
		{"role": "system", "content": state.system_prompt},
		{"role": "user", "content": user_prompt},
	])
	state.candidate_json = resp.content if hasattr(resp, "content") else str(resp)
	return state


async def node_validate_or_repair(state: AgentState, config: RunnableConfig) -> AgentState:
	"""Validate the candidate JSON; attempt a few automated repairs if needed."""
	max_repairs = int(config.get("max_repairs", 2))
	attempt = 0
	last_err = None
	llm = ChatOpenAI(model=config.get("model", "gpt-4o-mini"), temperature=0.0)
	while attempt <= max_repairs:
		try:
			validate_concepts_json(state.candidate_json or "")
			state.final_json = state.candidate_json
			state.error = None
			return state
		except Exception as e:
			last_err = str(e)
			repair_prompt = (
				"The previous JSON was invalid. Fix it to match the exact schema and guidance.\n"
				f"Error: {last_err}\n"
				"Return JSON only."
			)
			resp = await llm.ainvoke([
				{"role": "system", "content": state.system_prompt},
				{"role": "user", "content": repair_prompt},
			])
			state.candidate_json = resp.content if hasattr(resp, "content") else str(resp)
			attempt += 1
	state.final_json = state.candidate_json
	state.error = last_err
	return state
