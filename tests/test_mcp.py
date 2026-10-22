import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_freewatch import mcp_server


def test_initialize_and_tools_list():
    r = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert r["result"]["serverInfo"]["name"] == "llm-freewatch"
    r = mcp_server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = {t["name"] for t in r["result"]["tools"]}
    assert names == {"list_free_models", "free_model_changes", "free_providers"}


def test_unknown_method_and_notification():
    r = mcp_server.handle({"jsonrpc": "2.0", "id": 3, "method": "nope", "params": {}})
    assert r["error"]["code"] == -32601
    assert mcp_server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_free_providers_tool_offline():
    r = mcp_server.call_tool("free_providers", {})
    assert "Groq" in r["content"][0]["text"]
