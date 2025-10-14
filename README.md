# Clue Agent: ReAct + LangGraph PubMed Builder

This agent can construct pathology morphology concept lists per `src/prompt_template/p1.txt`, using PubMed (NCBI E-utilities) for search/observations and an LLM to synthesize and validate JSON outputs. Two execution engines are available: a simple ReAct loop and a LangGraph state graph.

## Setup

1. Python 3.10+
2. Install deps:

```bash
pip install -r requirements.txt
```

3. Configure environment:

- Copy `.env.example` to `.env` and set your keys.
  - `OPENAI_API_KEY` required
  - `NCBI_EMAIL` recommended (NIH policy)

## Run

- Original ReAct:
```bash
python -m src.main --engine react --dataset Camelyon16 --num-classes 2 --queries "lymph node metastasis carcinoma" "breast cancer lymph node metastasis"
```

- LangGraph pipeline:
```bash
python -m src.main --engine langraph --dataset Camelyon16 --num-classes 2 --queries "lymph node metastasis carcinoma" "breast cancer lymph node metastasis"
```

Output JSON is saved to `outputs/<dataset>.json`.

## Makefile

Convenience targets:

```bash
make install
make run-react
make run-lagraph
```

## How it works

- PubMed tools (`src/agent/pubmed.py`): wrappers for Entrez `esearch` (PMIDs) and `efetch` (abstracts), with sane timeouts, backoff, and NIH-friendly headers.
- Spec validator (`src/agent/spec.py`): Pydantic models that enforce the `p1.txt` JSON shape and basic cardinalities.
- ReAct loop (`src/agent/react_agent.py`): single-shot search/fetch; LLM synthesis; validate/repair attempts.
- LangGraph (`src/agent_lg/`): stateful graph: `search -> fetch -> synthesize -> validate` with configurable model and repair count.

Both engines render the `p1.txt` template with dataset context, provide PubMed observations to the LLM, and validate outputs, attempting structured repairs when needed.
