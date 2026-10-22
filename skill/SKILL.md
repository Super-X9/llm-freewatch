---
name: llm-freewatch
description: Check which free LLM models and free API tiers are actually available right now, before hard-coding a model id, wiring a fallback, or telling the user a free tier exists. Use when a task involves free models, OpenRouter :free models, fallback chains, or "is X still free" questions.
---

# llm-freewatch

Free model lineups rotate constantly. Never answer "which free models can I use"
from memory and never hard-code a `:free` model id without checking the live
catalog in this session.

## Steps

1. From the llm-freewatch repo root, run:
   `python3 -m llm_freewatch scan --tools`
   Add `--min-context <tokens>` when the task needs long context.
2. If the user has scanned before, read the diff lines (`+ added`, `- removed`)
   and call out any model the user's config depends on that disappeared.
3. When building a fallback, run `python3 -m llm_freewatch chain` (or
   `--format litellm`) and use the ordered chain instead of a single model.
4. For providers other than OpenRouter, run `python3 -m llm_freewatch providers`
   and report limits **with the verified date and the catch**. If the verified
   date is old, say the row may be stale instead of presenting it as current.
5. Probing is optional and needs the user's own `OPENROUTER_API_KEY` in the
   environment. Treat a `transient` verdict as "unknown, retry later", never
   as "the model is broken".

## Rules

- Distinguish live data (OpenRouter scan, fetched this session) from the
  curated provider table (human-verified snapshot) in everything you report.
- A model being listed as $0 does not mean unlimited: state the known rate
  limits when the user plans to build on a free tier.
