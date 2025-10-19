#!/usr/bin/env python3
"""CLI MCP chatbot that routes Anthropic tool calls to the ontology knowledge server."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import uuid
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict, List

import yaml
from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types as mcp_types
from mcp.client.stdio import stdio_client

load_dotenv()

CONFIG_PATH = os.environ.get("MCP_SERVER_CONFIG", "server_config.yaml")


class MCPChatBot:
    def __init__(self) -> None:
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.sessions: Dict[str, ClientSession] = {}
        self.available_tools: List[Dict[str, Any]] = []
        self.tool_to_session: Dict[str, ClientSession] = {}
        self.log_dir = Path(os.environ.get("CHATBOT_LOG_DIR", "documents/chat_logs"))

    async def connect(self, config_path: str = CONFIG_PATH) -> None:
        config = self._load_config(config_path)
        servers = config.get("servers")
        if not servers:
            raise RuntimeError("No MCP servers defined in config.")

        for name, server_cfg in servers.items():
            await self._connect_server(name, server_cfg)

        if not self.available_tools:
            raise RuntimeError("No tools available after connecting to servers.")

    def _load_config(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle) or {}
        except FileNotFoundError as exc:
            raise RuntimeError(f"MCP config not found at {path}") from exc

    def _build_stdio_params(self, cfg: Dict[str, Any]) -> StdioServerParameters:
        command = cfg.get("command")
        args = cfg.get("args")
        if isinstance(command, list):
            if not command:
                raise ValueError("command list must contain at least one item.")
            executable = command[0]
            merged_args = command[1:]
            if args:
                merged_args.extend(args if isinstance(args, list) else [args])
        else:
            executable = command
            if isinstance(args, list):
                merged_args = args[:]
            elif args:
                merged_args = [args]
            else:
                merged_args = []

        if not executable:
            raise ValueError("command is required for MCP server configuration.")

        env = cfg.get("env")
        return StdioServerParameters(command=executable, args=merged_args or None, env=env)

    async def _connect_server(self, name: str, cfg: Dict[str, Any]) -> None:
        params = self._build_stdio_params(cfg)
        read, write = await self.exit_stack.enter_async_context(stdio_client(params))
        session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self.sessions[name] = session

        tool_list = await session.list_tools()
        tools = tool_list.tools
        print(f"\nConnected to {name} with tools: {[tool.name for tool in tools]}")

        for tool in tools:
            schema: Any = tool.inputSchema
            if hasattr(schema, "model_dump"):
                schema = schema.model_dump()
            elif hasattr(schema, "to_dict"):
                schema = schema.to_dict()
            self.tool_to_session[tool.name] = session
            self.available_tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": schema or {},
                }
            )

    async def call_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> mcp_types.CallToolResult:
        session = self.tool_to_session.get(tool_name)
        if not session:
            raise ValueError(f"Tool '{tool_name}' is not registered.")
        return await session.call_tool(tool_name, arguments=tool_args or {})

    @staticmethod
    def _result_content_blocks(result: mcp_types.CallToolResult) -> List[Dict[str, str]]:
        blocks: List[Dict[str, str]] = []
        for item in result.content:
            text = getattr(item, "text", None)
            if text is None:
                try:
                    text = json.dumps(item.model_dump(), indent=2)
                except Exception:
                    text = str(item)
            blocks.append({"type": "text", "text": text})
        if not blocks:
            blocks.append({"type": "text", "text": ""})
        return blocks

    def _init_trace(self, query: str) -> Dict[str, Any]:
        trace_id = f"{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
        return {
            "trace_id": trace_id,
            "started_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "query": query,
            "events": [],
        }

    def _append_event(self, trace: Dict[str, Any], event: Dict[str, Any]) -> None:
        event["timestamp"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        trace["events"].append(event)

    def _write_trace(self, trace: Dict[str, Any]) -> None:
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            file_path = self.log_dir / f"{trace['trace_id']}.json"
            with file_path.open("w", encoding="utf-8") as handle:
                json.dump(trace, handle, indent=2, ensure_ascii=False)
            print(f"\n[trace] Conversation saved to {file_path}")
        except Exception as exc:
            print(f"\n[trace] Failed to save conversation trace: {exc}")

    async def process_query(self, query: str) -> None:
        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": [{"type": "text", "text": query}]}
        ]
        trace = self._init_trace(query)
        self._append_event(trace, {"type": "user", "text": query})

        try:
            response = self.anthropic.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=2024,
                tools=self.available_tools,
                messages=messages,
            )

            while True:
                assistant_payload: List[Dict[str, Any]] = []
                tool_requests: List[Any] = []

                for block in response.content:
                    if block.type == "text":
                        print(block.text)
                        assistant_payload.append({"type": "text", "text": block.text})
                        self._append_event(trace, {"type": "assistant_text", "text": block.text})
                    elif block.type == "tool_use":
                        print(f"Calling tool {block.name} with args {block.input}")
                        assistant_payload.append(
                            {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                        )
                        tool_requests.append(block)
                        self._append_event(
                            trace,
                            {
                                "type": "tool_use",
                                "tool_name": block.name,
                                "tool_use_id": block.id,
                                "input": block.input or {},
                            },
                        )

                messages.append({"role": "assistant", "content": assistant_payload})

                if not tool_requests:
                    break

                for tool_block in tool_requests:
                    try:
                        result = await self.call_tool(tool_block.name, tool_block.input or {})
                        result_blocks = self._result_content_blocks(result)
                        self._append_event(
                            trace,
                            {
                                "type": "tool_result",
                                "tool_name": tool_block.name,
                                "tool_use_id": tool_block.id,
                                "content": result_blocks,
                            },
                        )
                    except Exception as exc:
                        error_text = f"Error calling tool '{tool_block.name}': {exc}"
                        print(error_text)
                        result_blocks = [{"type": "text", "text": error_text}]
                        self._append_event(
                            trace,
                            {
                                "type": "tool_error",
                                "tool_name": tool_block.name,
                                "tool_use_id": tool_block.id,
                                "error": str(exc),
                            },
                        )

                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_block.id,
                                    "content": result_blocks,
                                }
                            ],
                        }
                    )

                response = self.anthropic.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=2024,
                    tools=self.available_tools,
                    messages=messages,
                )
        finally:
            self._write_trace(trace)

    async def chat_loop(self) -> None:
        print("\nMCP Chatbot Started!")
        print("Type queries or 'quit' to exit.")

        while True:
            try:
                query = (await asyncio.to_thread(input, "\nQuery: ")).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting chat.")
                break

            if not query:
                continue
            if query.lower() == "quit":
                break

            try:
                await self.process_query(query)
                print()
            except Exception as exc:
                print(f"\nError: {exc}")

    async def cleanup(self) -> None:
        await self.exit_stack.aclose()


async def main() -> None:
    chatbot = MCPChatBot()
    try:
        await chatbot.connect()
        await chatbot.chat_loop()
    finally:
        await chatbot.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
