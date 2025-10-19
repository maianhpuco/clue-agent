.PHONY: help install run-react run-lagraph lint create_concept query_planner_example ont-react tools-agent-v2

help:
	@echo "Targets:"
	@echo "  install              - Install Python dependencies"
	@echo "  run-react            - Run original ReAct pipeline"
	@echo "  run-lagraph          - Run LangGraph pipeline"
	@echo "  create_concept       - Build concepts for Camelyon16 (LangGraph)"
	@echo "  query_planner_example- Demo query planner"
	@echo "  ont-react            - Run dataset-agnostic ReAct ontology agent"
	@echo "  tools-agent-v2       - Run tools_agent_v2 split pipeline"

install:
	pip install -r requirements.txt

create_concept:
	python -m src.main --engine langraph --dataset Camelyon16 --num-classes 2 --classes Tumor Normal --save-intermediate

query_planner_example:
	python -m src.agent.query_planner.example_run

ont-react:
	python -m src.agent_ont.react_pathology_agent --dataset camelyon16 --outdir runs/c16 --max_iters 3 --k 5

tools-agent-v2:
	python -m src.agent_ont.tools_agent_v2 --model $${OPENAI_MODEL:-gpt-4o-mini} --outdir runs/react_split --class_name "breast carcinoma lymph node metastasis" --k 5 --max_iters 3 --min_concepts 4

ex1:
	python -m src.agent_ont.react_pathology_agent \
	  --dataset camelyon16 \
	  --label_desc "breast carcinoma metastasis in sentinel lymph node" \
	  --outdir runs/c16_simple \
	  --k 5 \
	  --model gpt-4o-mini 

query-searches:
	python tools/inspect_ontology_db.py searches

query-results:
	python tools/inspect_ontology_db.py results

query-extractions:
	python tools/inspect_ontology_db.py extractions
# lint:
# 	python -m pyflakes src || true

    
#     ```
#   - Only tumor-focused search (still generates JSON for both classes due to the template/meta):
#     ```bash
#     python -m src.main --engine langraph --dataset Camelyon16 --num-classes 2 --classes Tumor --save-intermediate
#     ```

# Notes:
# - --classes derives queries internally (e.g., "Camelyon16 Tumor", "Camelyon16 Normal"). Meta from `meta_camelyon16.txt` is auto-injected into the prompt.
# - --save-intermediate writes:
#   - outputs/intermediate/Camelyon16.pmids.json
#   - outputs/intermediate/Camelyon16.abstracts.json
# - Keep `--num-classes 2` for Camelyon16 even if you only pass `Tumor` to bias search.





#   python -m src.agent_ont.react_pathology_agent --dataset camelyon16 --outdir runs/c16 --max_iters 3 --k 5
#   python -m src.agent_ont.react_pathology_agent --dataset tcga_lung  --outdir runs/lung --max_iters 3 --k 5
#   python -m src.agent_ont.react_pathology_agent --dataset tcga_renal --outdir runs/renal --max_iters 3 --k 5
#   ```

# Outputs (per iteration):
# - search_terms_iterX_TIMESTAMP.json
# - results_iterX_TIMESTAMP.json
# - summaries_iterX_TIMESTAMP.json
# - mutated_terms_iterX_TIMESTAMP.json (if continuing)
# - final_yaml_stub_TIMESTAMP.json when coverage met

# Notes:
# - Replace `tool_search` and `call_llm` with your real backends (PubMed/SerpAPI/local notes + your LLM).
# - Adjust `TOKEN_MAP` and thresholds in `check_coverage` for stricter clinical rules. 
