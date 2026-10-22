"""Core logic for llm-freewatch.

Design rules:
- Python standard library only. No third-party imports, ever.
- Live data comes from public provider APIs (OpenRouter today).
  Providers without a public catalog API are shipped as a curated
  data file where every row carries its source URL and the date it
  was last verified by a human. Curated rows are never presented
  as live data.
- API keys are read from the environment at call time only and
  are never stored, logged, or written to disk.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
USER_AGENT = "llm-freewatch/0.1.0 (+https://openrouter.ai/api/v1/models)"


def _get_json(url: str, timeout: int = 30) -> dict:
    """GET JSON with retries.

    Some proxies mangle chunked responses for urllib (IncompleteRead);
    when that happens and curl is available, fall back to it. This is
    deliberate: the tool is meant to run unattended behind whatever
    network the user happens to have.
    """
    last_exc = None
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # retry, then curl fallback
            last_exc = e
            time.sleep(1)
    import shutil
    import subprocess

    curl = shutil.which("curl")
    if curl:
        out = subprocess.run(
            [curl, "-fsSL", "--max-time", str(timeout), "-A", USER_AGENT, url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        if out.returncode == 0:
            return json.loads(out.stdout)
    raise RuntimeError(f"failed to fetch {url}: {last_exc}")


def _price_is_zero(value) -> bool:
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


def parse_openrouter_models(payload: dict) -> list[dict]:
    """Turn an OpenRouter /models payload into normalized free-model rows."""
    rows = []
    for m in payload.get("data", []):
        pricing = m.get("pricing") or {}
        if not (_price_is_zero(pricing.get("prompt")) and _price_is_zero(pricing.get("completion"))):
            continue
        arch = m.get("architecture") or {}
        params = m.get("supported_parameters") or []
        rows.append(
            {
                "provider": "openrouter",
                "id": m.get("id", ""),
                "name": m.get("name", m.get("id", "")),
                "context_length": m.get("context_length") or 0,
                "tools": "tools" in params,
                "input_modalities": arch.get("input_modalities") or [],
                "output_modalities": arch.get("output_modalities") or [],
            }
        )
    return rows


def fetch_openrouter_free() -> list[dict]:
    return parse_openrouter_models(_get_json(OPENROUTER_MODELS_URL))


def load_curated_providers() -> list[dict]:
    path = Path(__file__).with_name("providers.json")
    return json.loads(path.read_text(encoding="utf-8"))


def filter_models(models: list[dict], tools_only: bool = False, min_context: int = 0) -> list[dict]:
    out = [
        m
        for m in models
        if (not tools_only or m.get("tools"))
        and int(m.get("context_length") or 0) >= min_context
    ]
    return rank_models(out)


def rank_models(models: list[dict]) -> list[dict]:
    """Tool-calling first, then biggest context. Deterministic order."""
    return sorted(
        models,
        key=lambda m: (not m.get("tools"), -int(m.get("context_length") or 0), m.get("id", "")),
    )


def diff_models(old: list[dict], new: list[dict]) -> dict:
    old_ids = {m["id"] for m in old}
    new_ids = {m["id"] for m in new}
    return {
        "added": sorted(new_ids - old_ids),
        "removed": sorted(old_ids - new_ids),
        "kept": sorted(old_ids & new_ids),
    }


def save_cache(models: list[dict], cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"fetched_at": int(time.time()), "models": models}, indent=2),
        encoding="utf-8",
    )


def load_cache(cache_path: Path) -> list[dict]:
    if not cache_path.exists():
        return []
    try:
        return json.loads(cache_path.read_text(encoding="utf-8")).get("models", [])
    except (json.JSONDecodeError, OSError):
        return []


def default_cache_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "llm-freewatch" / "last_scan.json"


def build_chain(models: list[dict], limit: int = 5) -> dict:
    """An ordered fallback chain an agent can walk when a model 429s or vanishes."""
    ranked = rank_models(models)[:limit]
    return {
        "generated_by": "llm-freewatch",
        "strategy": "tools-first, then largest context; walk in order on 429/404/5xx",
        "models": [m["id"] for m in ranked],
        "details": ranked,
    }


def chain_to_litellm_yaml(chain: dict) -> str:
    lines = ["model_list:"]
    for i, mid in enumerate(chain["models"]):
        lines.append(f"  - model_name: free-{i}")
        lines.append(f"    litellm_params:")
        lines.append(f"      model: openrouter/{mid}")
        lines.append(f"      api_base: https://openrouter.ai/api/v1")
        lines.append(f"      api_key: os.environ/OPENROUTER_API_KEY")
    lines.append("fallbacks:")
    lines.append("  - " + json.dumps({f"free-{i}": [f"free-{j}" for j in range(len(chain["models"])) if j != i] for i in range(len(chain["models"]))}))
    return "\n".join(lines) + "\n"


def classify_http(status: int) -> str:
    if status == 200:
        return "ok"
    if status in (408, 409, 429) or status >= 500:
        return "transient"
    return "hard"


def probe_model(model_id: str, api_key: str, timeout: int = 45) -> dict:
    """One real tool-call probe. The model must call get_weather(city=...).

    Returns a verdict dict; 'transient' results are explicitly not a verdict
    on the model (rate limit / upstream blip), mirroring how agents should
    treat them in production.
    """
    body = {
        "model": model_id,
        "messages": [{"role": "user", "content": "What is the weather in Reykjavik? Use the tool."}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                },
            }
        ],
        "tool_choice": "auto",
        "max_tokens": 256,
    }
    req = urllib.request.Request(
        OPENROUTER_CHAT_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            status = resp.status
    except urllib.error.HTTPError as e:
        return {"model": model_id, "verdict": classify_http(e.code), "http": e.code}
    except Exception as e:  # network timeouts etc. are transient by definition
        return {"model": model_id, "verdict": "transient", "error": type(e).__name__}
    latency_ms = int((time.time() - started) * 1000)
    try:
        msg = payload["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        for call in calls:
            fn = call.get("function") or {}
            if fn.get("name") == "get_weather":
                args = json.loads(fn.get("arguments") or "{}")
                if "reykjavik" in str(args.get("city", "")).lower():
                    return {"model": model_id, "verdict": "ok", "http": status, "latency_ms": latency_ms}
        return {"model": model_id, "verdict": "hard", "http": status, "reason": "no valid tool call"}
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return {"model": model_id, "verdict": "hard", "http": status, "reason": "unparseable response"}


def models_to_markdown(models: list[dict], title: str, generated_at: str) -> str:
    lines = [f"# {title}", "", f"_Generated {generated_at} by llm-freewatch (live OpenRouter catalog)._", ""]
    lines.append(f"**{len(models)} free models** (prompt and completion price both $0).")
    lines.append("")
    lines.append("| Model | Context | Tool calling |")
    lines.append("|---|---:|:---:|")
    for m in rank_models(models):
        ctx = f"{int(m['context_length']):,}" if m.get("context_length") else "?"
        lines.append(f"| `{m['id']}` | {ctx} | {'yes' if m.get('tools') else 'no'} |")
    lines.append("")
    return "\n".join(lines)
