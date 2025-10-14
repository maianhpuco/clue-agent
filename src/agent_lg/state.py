from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class AgentState(BaseModel):
	"""Shared state passed between LangGraph nodes.

	- dataset_name/num_classes/queries: inputs defining the problem space.
	- pmids: PubMed IDs discovered by the search node.
	- abstracts: PMID->abstract text gathered by the fetch node.
	- system_prompt: rendered prompt from template with dataset and class count.
	- candidate_json: latest LLM JSON attempt.
	- final_json: validated JSON output (when available).
	- error: last validation error message (if any).
	"""

	dataset_name: str
	num_classes: int
	queries: List[str]
	pmids: List[str] = Field(default_factory=list)
	abstracts: Dict[str, str] = Field(default_factory=dict)
	system_prompt: str = ""
	candidate_json: Optional[str] = None
	final_json: Optional[str] = None
	error: Optional[str] = None
