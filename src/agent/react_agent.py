import asyncio
import os
from typing import List, Dict, Any, Optional, Tuple
from rich.console import Console
from rich.panel import Panel

from .pubmed import pubmed_esearch, pubmed_efetch_abstracts
from .llm import LLMClient
from .spec import validate_concepts_json

console = Console()


def build_user_prompt(queries: List[str], abstracts: Dict[str, str]) -> str:
	"""Assemble a bounded observation buffer for the LLM user message."""
	observations = []
	for pmid, text in abstracts.items():
		observations.append(f"PMID {pmid}:\n{text}")
	obs_text = "\n\n".join(observations[:20])  # keep prompt bounded
	q_text = "\n".join(f"- {q}" for q in queries)
	return (
		"You can use the following observations from PubMed abstracts to construct the JSON list.\n"
		"Queries used:\n" + q_text + "\n\n"
		"Observations (subset):\n" + obs_text + "\n\n"
		"Return only JSON per the spec."
	)


async def run_react(system_prompt: str, dataset_name: str, num_classes: int, queries: List[str],
					 model: Optional[str] = None, max_iters: int = 3) -> Tuple[str, List[str], Dict[str, str]]:
	"""ReAct-style loop: search/fetch observations -> LLM synthesis -> validate/repair.

	Returns: (best_json, pmids, abstracts)
	"""
	llm = LLMClient(model=model)
	console.print(Panel.fit("Searching PubMed...", title="ReAct"))
	pmids_all: List[str] = []
	for q in queries:
		ids = await pubmed_esearch(q, retmax=25)
		pmids_all.extend(ids)
	pmids_all = list(dict.fromkeys(pmids_all))[:60]

	abstracts = await pubmed_efetch_abstracts(pmids_all)

	exception: Optional[Exception] = None
	last_text: str = ""
	for i in range(max_iters):
		user_prompt = build_user_prompt(queries, abstracts)
		console.print(Panel.fit(f"LLM synthesis attempt {i+1}/{max_iters}", title="ReAct"))
		candidate = await asyncio.to_thread(llm.complete_json, system_prompt, user_prompt)
		last_text = candidate
		try:
			_ = validate_concepts_json(candidate)
			return candidate, pmids_all, abstracts
		except Exception as e:
			exception = e
			repair_prompt = (
				"The previous JSON was invalid. Fix it to match the exact schema and guidance.\n"
				f"Error: {e}\n"
				"Return JSON only."
			)
			candidate = await asyncio.to_thread(llm.complete_json, system_prompt, repair_prompt)
			last_text = candidate
			try:
				_ = validate_concepts_json(candidate)
				return candidate, pmids_all, abstracts
			except Exception as e2:
				exception = e2

	if exception:
		console.print(f"Validation failed after {max_iters} iterations: {exception}")
	return last_text, pmids_all, abstracts
