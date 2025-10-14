import argparse
import asyncio
import os
from pathlib import Path
from rich.console import Console
import json
from dotenv import load_dotenv

from .agent.react_agent import run_react
from .agent_lg.graph import run_graph_async
from .agent_lg.state import AgentState

# Load variables from a local .env file if present
load_dotenv()

console = Console()


def load_template() -> str:
	template_path = Path(__file__).parent / "prompt_template" / "p1.txt"
	return template_path.read_text(encoding="utf-8")


def load_meta(dataset: str) -> str:
	meta_path = Path(__file__).parent / "prompt_template" / f"meta_{dataset.lower()}.txt"
	return meta_path.read_text(encoding="utf-8") if meta_path.exists() else ""


def render_system(template_text: str, dataset: str, num_classes: int, class_desc: str) -> str:
	return (
		template_text
		.replace("{{DATASET_NAME}}", dataset)
		.replace("{{NUM_CLASSES}}", str(num_classes))
		.replace("{{CLASS_DESCRIPTIONS}}", class_desc or "")
	)


async def amain():
	parser = argparse.ArgumentParser(description="ReAct/LangGraph PubMed builder for pathology morphology JSON")
	parser.add_argument("--dataset", required=True)
	parser.add_argument("--num-classes", type=int, required=True)
	parser.add_argument("--queries", nargs="*")
	parser.add_argument("--classes", nargs="*", help="Optional class names to derive queries from")
	parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
	parser.add_argument("--engine", choices=["react", "langraph"], default="react")
	parser.add_argument("--output", default=None)
	parser.add_argument("--save-intermediate", action="store_true")
	args = parser.parse_args()

	template_text = load_template()
	meta_text = load_meta(args.dataset)
	system_prompt = render_system(template_text, args.dataset, args.num_classes, meta_text)

	queries = args.queries or []
	if (not queries) and args.classes:
		queries = [f"{args.dataset} {c}" for c in args.classes]

	out_dir = Path("outputs")
	inter_dir = out_dir / "intermediate"
	if args.save_intermediate:
		inter_dir.mkdir(parents=True, exist_ok=True)

	if args.engine == "react":
		result, pmids, abstracts = await run_react(system_prompt, args.dataset, args.num_classes, queries, model=args.model)
		if args.save_intermediate:
			(inter_dir / f"{args.dataset}.pmids.json").write_text(json.dumps(pmids, ensure_ascii=False, indent=2), encoding="utf-8")
			(inter_dir / f"{args.dataset}.abstracts.json").write_text(json.dumps(abstracts, ensure_ascii=False, indent=2), encoding="utf-8")
	else:
		state = AgentState(
			dataset_name=args.dataset,
			num_classes=args.num_classes,
			queries=queries,
			system_prompt=system_prompt,
		)
		final_state = await run_graph_async(state, args.model, 2)
		# final_state is a mapping (AddableValuesDict). Extract safely.
		pmids = list((final_state.get("pmids") or []))  # type: ignore[attr-defined]
		abstracts = dict((final_state.get("abstracts") or {}))  # type: ignore[attr-defined]
		if args.save_intermediate:
			(inter_dir / f"{args.dataset}.pmids.json").write_text(json.dumps(pmids, ensure_ascii=False, indent=2), encoding="utf-8")
			(inter_dir / f"{args.dataset}.abstracts.json").write_text(json.dumps(abstracts, ensure_ascii=False, indent=2), encoding="utf-8")
		result = (final_state.get("final_json") or final_state.get("candidate_json") or "")  # type: ignore[attr-defined]

	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = Path(args.output) if args.output else out_dir / f"{args.dataset}.json"
	out_path.write_text(result, encoding="utf-8")
	console.print(f"Wrote {out_path}")


def main():
	asyncio.run(amain())


if __name__ == "__main__":
	main()
