# Contributing

The most valuable contribution is keeping data honest:

- **Curated provider rows** (`llm_freewatch/providers.json`): if a free tier
  changed, update the row, its `source` (the provider's own page or a dated
  check) and its `verified` date together. A row without a fresh date is a bug.
- **New live providers**: if a provider exposes a public catalog API, add a
  parser next to `parse_openrouter_models` with a fixture-based test.
- **Code**: standard library only. PRs adding a third-party dependency will be
  asked to remove it — zero-dependency is a feature users rely on.

Run `python -m pytest tests/ -q` before opening a PR.
