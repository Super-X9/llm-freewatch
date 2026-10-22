# llm-freewatch

**Know which free LLM APIs still work today — before your agent finds out the hard way.**

Free LLM tiers churn constantly: models appear and vanish, limits change without
notice, and whole programs get retired (GitHub Models shut down on 2026-07-30 and
old blog posts still recommend it). If your coding agent, side project, or demo is
wired to a hard-coded "free" model id, it breaks silently.

`llm-freewatch` is a zero-dependency Python tool that keeps an eye on the free
landscape for you:

- **Live radar** — fetches the live OpenRouter catalog and lists models that are
  *actually* free right now (prompt **and** completion price both $0), with context
  length and tool-calling support.
- **Change diffs** — every scan is diffed against the previous one, so you see which
  free models were **added or removed** since yesterday.
- **Fallback chains** — prints an ordered chain of free, tool-calling models (JSON,
  or a ready-to-use LiteLLM config) to walk when one model returns 429/404.
- **Real probes** — optionally runs one genuine tool-call against a model with your
  own key and classifies the result `ok` / `hard` / `transient`. A 429 is reported
  as *transient — not a verdict*, never as "the model is broken".
- **Curated providers** — for providers without a public catalog API (Groq, Google
  Gemini, NVIDIA NIM, Mistral, Cloudflare Workers AI, Cohere), ships a curated table
  where **every row carries its source URL and human-verified date**, including the
  catches (card rules, training use, trial-only). Curated rows are never disguised
  as live data.
- **MCP server** — runs over stdio, so Claude Code / Codex / Cursor agents can ask
  mid-task: *"which free models can I use right now?"* instead of guessing.
- **Agent skill** — ships a `SKILL.md` (see `skill/`) that teaches agents when and
  how to check the free lineup before hard-coding a model.

Zero third-party dependencies. Python 3.10+ standard library only.

## Quick start

```bash
git clone <this repo>
cd llm-freewatch
python3 -m llm_freewatch scan --tools        # what is free + tool-capable right now
python3 -m llm_freewatch providers           # curated free tiers, limits and catches
python3 -m llm_freewatch chain               # ordered fallback chain (JSON)
python3 -m llm_freewatch chain --format litellm > litellm_config.yaml
```

Example output (live, 2026-10-22):

```
MODEL                                                        CONTEXT  TOOLS
thinkingmachines/inkling:free                              1,048,576  yes
nvidia/nemotron-3-ultra-550b-a55b:free                     1,000,000  yes
google/gemma-4-31b-it:free                                   262,144  yes
...
18 free models.
```

The current snapshot is regenerated daily in [`docs/FREE_MODELS.md`](docs/FREE_MODELS.md).

## Probe a model for real (optional)

```bash
export OPENROUTER_API_KEY=...   # your own key; read from env only, never stored
python3 -m llm_freewatch probe nvidia/nemotron-3-super-120b-a12b:free
# {"model": "...", "verdict": "ok", "http": 200, "latency_ms": 812}
```

## Use it as an MCP server

```json
{
  "mcpServers": {
    "llm-freewatch": {
      "command": "python3",
      "args": ["-m", "llm_freewatch", "mcp"],
      "cwd": "/path/to/llm-freewatch"
    }
  }
}
```

Tools: `list_free_models`, `free_model_changes`, `free_providers`.

## Why this exists

This project grew out of running a personal coding agent on free models: the free
lineup rotated often enough that a daily radar + diff became the difference between
"agent works" and "agent silently fails". The same churn is documented publicly —
free-tier roundups in October 2026 all warn that the limits and lineups they list
will be wrong soon. A list goes stale; a watcher doesn't.

## Honest limits

- Only the OpenRouter catalog is fetched live today. Other providers are curated
  snapshots with sources and dates, and they *will* drift — PRs updating a row must
  update its `verified` date and source.
- "Free" means the provider lists $0 pricing. Free tiers have rate limits (for
  OpenRouter free models, typically 20 RPM and 50 requests/day on a free account)
  and providers may log or train on free-tier prompts. Check each provider's terms.
- A probe `ok` means one tool call worked once. It is a smoke test, not a benchmark.

## Development

```bash
python3 -m pytest tests/ -q     # or run the test modules with any runner
```

## License

MIT

---

中文说明见 [README.zh-CN.md](README.zh-CN.md)。
