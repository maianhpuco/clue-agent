#!/usr/bin/env python3
"""Render conversation traces from chatbot logs as Mermaid diagrams."""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List


def load_trace(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sanitize_label(text: str, width: int = 40) -> str:
    text = str(text).replace("\r", " ").strip()
    if not text:
        text = "(empty)"
    wrapped = textwrap.fill(text, width=width)
    return wrapped.replace("\n", "\\n").replace('"', '\\"')


def event_label(event: Dict[str, Any]) -> str:
    etype = event.get("type", "event")
    if etype == "user":
        return f"User: {sanitize_label(event.get('text', ''))}"
    if etype == "assistant_text":
        return f"Assistant: {sanitize_label(event.get('text', ''))}"
    if etype == "tool_use":
        tool = event.get("tool_name", "?")
        args = sanitize_label(json.dumps(event.get("input", {}), ensure_ascii=False))
        return f"Tool call: {tool}\\nargs={args}"
    if etype == "tool_result":
        tool = event.get("tool_name", "?")
        content = event.get("content", [])
        snippets: List[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if text:
                    snippets.append(text)
        summary = sanitize_label(" | ".join(snippets) if snippets else json.dumps(content, ensure_ascii=False))
        return f"Tool result: {tool}\\n{summary}"
    if etype == "tool_error":
        tool = event.get("tool_name", "?")
        return f"Tool error: {tool}\\n{sanitize_label(event.get('error', ''))}"
    return f"{etype}: {sanitize_label(json.dumps(event, ensure_ascii=False))}"


def build_mermaid(trace: Dict[str, Any]) -> str:
    events = trace.get("events", [])
    nodes = []
    edges = []
    classes = []
    tool_map: Dict[str, str] = {}

    for idx, event in enumerate(events):
        node_id = f"n{idx}"
        label = event_label(event)
        etype = event.get("type", "event")

        nodes.append(f'  {node_id}["{label}"]')

        if idx < len(events) - 1:
            edges.append(f"  {node_id} --> n{idx + 1}")

        if etype == "user":
            classes.append(f"  class {node_id} user;")
        elif etype == "assistant_text":
            classes.append(f"  class {node_id} assistant;")
        elif etype == "tool_use":
            classes.append(f"  class {node_id} tool;")
            tool_map[event.get("tool_use_id", "")] = node_id
        elif etype in ("tool_result", "tool_error"):
            classes.append(f"  class {node_id} result;")
            tool_id = event.get("tool_use_id")
            if tool_id and tool_id in tool_map:
                edges.append(f"  {tool_map[tool_id]} -.-> {node_id}")
        else:
            classes.append(f"  class {node_id} other;")

    header = [
        "graph TD",
        "  classDef user fill:#E3F2FD,stroke:#1E88E5,color:#0D47A1;",
        "  classDef assistant fill:#F3E5F5,stroke:#8E24AA,color:#4A148C;",
        "  classDef tool fill:#FFF3E0,stroke:#FB8C00,color:#E65100;",
        "  classDef result fill:#E8F5E9,stroke:#43A047,color:#1B5E20;",
        "  classDef other fill:#ECEFF1,stroke:#607D8B,color:#37474F;",
    ]

    lines = header + nodes + edges + classes
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render chatbot trace as a Mermaid diagram.")
    parser.add_argument(
        "trace_path",
        help="Path to a trace JSON file created by chatbot.py (documents/chat_logs/...json).",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the Mermaid diagram. Prints to stdout if omitted.",
    )
    args = parser.parse_args()

    trace_file = Path(args.trace_path)
    if not trace_file.exists():
        raise SystemExit(f"Trace file not found: {trace_file}")

    trace = load_trace(trace_file)
    mermaid = build_mermaid(trace)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(mermaid, encoding="utf-8")
        print(f"Mermaid diagram written to {out_path}")
    else:
        print(mermaid)


if __name__ == "__main__":
    main()
