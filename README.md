# Ontology MCP Workspace

This workspace wires an MCP server for ontology lookups together with a CLI chatbot. The chatbot now records each interaction, and helper scripts let you inspect cached searches or visualise the conversation flow.

## Conversation logging & visualisation

- Run `python chatbot.py` as usual; every query saves a trace JSON under `documents/chat_logs/` (configurable via `CHATBOT_LOG_DIR`).
- Render a Mermaid graph from any trace with:
  ```bash
  python tools/render_chat_graph.py documents/chat_logs/<trace-id>.json
  ```
  Paste the Mermaid output into https://mermaid.live or any Mermaid renderer to view the conversation → tool invocation graph.

## Inspecting the ontology cache

- `make query-searches` – most recent rows in the `searches` table.
- `make query-results` – cached provider result payloads.
- `make query-extractions` – stored ontology extraction prompts and outputs.

## Quick dataset sanity check

Example synonyms for “metastatic breast carcinoma in lymph-node tissue” (handy when testing terminology tools):

- Lymph node metastasis
- Metastatic carcinoma in lymph node(s)
- Nodal metastasis
- Secondary carcinoma of lymph node
- Metastatic involvement of lymph node
