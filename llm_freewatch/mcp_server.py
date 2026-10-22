"""Minimal MCP server over stdio (JSON-RPC 2.0), standard library only.

Implements just enough of the Model Context Protocol for an agent
(Claude Code, Codex, Cursor, ...) to ask, mid-task:
  - which free models can I actually use right now?
  - what changed since yesterday?
  - which other providers still have a real free tier?
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import core

PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "list_free_models",
        "description": "List currently free models from the live OpenRouter catalog. "
                       "Optionally require tool calling and a minimum context length.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tools_only": {"type": "boolean", "default": False},
                "min_context": {"type": "integer", "default": 0},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "free_model_changes",
        "description": "Diff the live free catalog against the last local scan: which free "
                       "models appeared or disappeared. Free lineups rotate; check before "
                       "hard-coding a model id.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "free_providers",
        "description": "Curated, human-verified free tiers for providers without a public "
                       "catalog API (Groq, Gemini, NVIDIA NIM, Mistral, Cloudflare, Cohere), "
                       "with limits, card rules and catches, each with source and verified date.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _text(payload) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


def call_tool(name: str, arguments: dict) -> dict:
    if name == "list_free_models":
        models = core.fetch_openrouter_free()
        models = core.filter_models(
            models,
            tools_only=bool(arguments.get("tools_only", False)),
            min_context=int(arguments.get("min_context", 0)),
        )
        limit = int(arguments.get("limit", 20))
        return _text({"count": len(models), "models": models[:limit]})
    if name == "free_model_changes":
        cache = core.default_cache_path()
        old = core.load_cache(cache)
        new = core.fetch_openrouter_free()
        change = core.diff_models(old, new)
        core.save_cache(new, cache)
        return _text(change)
    if name == "free_providers":
        return _text(core.load_curated_providers())
    return {"content": [{"type": "text", "text": f"unknown tool: {name}"}], "isError": True}


def handle(msg: dict) -> dict | None:
    method = msg.get("method", "")
    mid = msg.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "llm-freewatch", "version": "0.1.0"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params") or {}
        try:
            result = call_tool(params.get("name", ""), params.get("arguments") or {})
        except Exception as e:
            result = {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    if mid is not None:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def serve() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    return 0
