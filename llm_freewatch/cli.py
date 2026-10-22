from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import core


def _print_table(models: list[dict]) -> None:
    print(f"{'MODEL':<58} {'CONTEXT':>9}  TOOLS")
    for m in models:
        ctx = f"{int(m['context_length']):,}" if m.get("context_length") else "?"
        print(f"{m['id']:<58} {ctx:>9}  {'yes' if m.get('tools') else 'no'}")


def cmd_scan(args) -> int:
    models = core.fetch_openrouter_free()
    cache = Path(args.cache) if args.cache else core.default_cache_path()
    old = core.load_cache(cache)
    change = core.diff_models(old, models) if old else {"added": [], "removed": [], "kept": []}
    core.save_cache(models, cache)
    models = core.filter_models(models, tools_only=args.tools, min_context=args.min_context)
    if args.json:
        print(json.dumps({"count": len(models), "models": models, "changes": change}, indent=2))
    elif args.markdown:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        print(core.models_to_markdown(models, "Free models on OpenRouter right now", now))
    else:
        _print_table(models)
        print(f"\n{len(models)} free models. Cache: {cache}")
        if old:
            print(f"Since last scan: +{len(change['added'])} added, -{len(change['removed'])} removed")
            for mid in change["added"]:
                print(f"  + {mid}")
            for mid in change["removed"]:
                print(f"  - {mid}")
    return 0


def cmd_providers(args) -> int:
    rows = core.load_curated_providers()
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    for r in rows:
        print(f"## {r['provider']}  (verified {r['verified']})")
        print(f"  Free:    {r['free_tier']}")
        print(f"  Limits:  {r['limits']}")
        print(f"  Card:    {r['card_required']}")
        print(f"  Catch:   {r['catch']}")
        print(f"  Source:  {r['source']}")
        print()
    print("Curated rows are human-verified snapshots, not live data. Only the")
    print("OpenRouter catalog (scan/list/chain) is fetched live.")
    return 0


def cmd_chain(args) -> int:
    models = core.fetch_openrouter_free()
    models = core.filter_models(models, tools_only=True, min_context=args.min_context)
    chain = core.build_chain(models, limit=args.limit)
    if args.format == "litellm":
        print(core.chain_to_litellm_yaml(chain), end="")
    else:
        print(json.dumps(chain, indent=2))
    return 0


def cmd_probe(args) -> int:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        print("OPENROUTER_API_KEY is not set. Probing needs your own key; it is read "
              "from the environment only and never stored.", file=sys.stderr)
        return 2
    targets = args.models
    if not targets:
        free = core.filter_models(core.fetch_openrouter_free(), tools_only=True)
        targets = [m["id"] for m in free[: args.limit]]
    for mid in targets:
        result = core.probe_model(mid, key)
        print(json.dumps(result))
    return 0


def cmd_mcp(args) -> int:
    from .mcp_server import serve

    return serve()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="llm-freewatch", description="Watch free LLM APIs the way your agent wishes you would.")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="Fetch the live free catalog, diff against the last scan")
    s.add_argument("--tools", action="store_true", help="Only models advertising tool calling")
    s.add_argument("--min-context", type=int, default=0)
    s.add_argument("--json", action="store_true")
    s.add_argument("--markdown", action="store_true")
    s.add_argument("--cache", default="")
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("providers", help="Curated free tiers for providers without a public catalog API")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_providers)

    s = sub.add_parser("chain", help="Print an ordered fallback chain of free tool-calling models")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--min-context", type=int, default=0)
    s.add_argument("--format", choices=["json", "litellm"], default="json")
    s.set_defaults(fn=cmd_chain)

    s = sub.add_parser("probe", help="Run one real tool-call probe per model (needs OPENROUTER_API_KEY)")
    s.add_argument("models", nargs="*")
    s.add_argument("--limit", type=int, default=5)
    s.set_defaults(fn=cmd_probe)

    s = sub.add_parser("mcp", help="Run as an MCP server over stdio")
    s.set_defaults(fn=cmd_mcp)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
