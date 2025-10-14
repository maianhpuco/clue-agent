from typing import Optional
from langgraph.graph import StateGraph, END
from langgraph.types import RunnableConfig

from .state import AgentState
from .nodes import node_search, node_fetch, node_synthesize, node_validate_or_repair

__all__ = ["run_graph_async", "build_graph"]


def build_graph() -> StateGraph:
	"""Build a simple linear LangGraph:
	search -> fetch -> synthesize -> validate -> END
	"""
	g = StateGraph(AgentState)
	g.add_node("search", node_search)
	g.add_node("fetch", node_fetch)
	g.add_node("synthesize", node_synthesize)
	g.add_node("validate", node_validate_or_repair)

	g.set_entry_point("search")
	g.add_edge("search", "fetch")
	g.add_edge("fetch", "synthesize")
	g.add_edge("synthesize", "validate")
	g.add_edge("validate", END)
	return g


async def run_graph_async(state: AgentState, model: Optional[str] = None, max_repairs: int = 2) -> AgentState:
	"""Compile and run the graph asynchronously (for async nodes)."""
	graph = build_graph().compile()
	config: RunnableConfig = {"configurable": {"model": model or "gpt-4o-mini", "max_repairs": max_repairs}}
	return await graph.ainvoke(state, config=config)
