import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_freewatch import core


def load_sample():
    path = Path(__file__).parent / "fixtures" / "openrouter_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_parse_keeps_only_fully_free():
    rows = core.parse_openrouter_models(load_sample())
    ids = {r["id"] for r in rows}
    assert ids == {"acme/big-1:free", "acme/small-2:free"}


def test_parse_fields():
    rows = {r["id"]: r for r in core.parse_openrouter_models(load_sample())}
    assert rows["acme/big-1:free"]["tools"] is True
    assert rows["acme/small-2:free"]["tools"] is False
    assert rows["acme/small-2:free"]["input_modalities"] == ["text", "image"]


def test_filter_tools_and_context():
    rows = core.parse_openrouter_models(load_sample())
    assert [r["id"] for r in core.filter_models(rows, tools_only=True)] == ["acme/big-1:free"]
    assert [r["id"] for r in core.filter_models(rows, min_context=100000)] == ["acme/big-1:free"]
    # ranking: tools first, then context
    assert [r["id"] for r in core.filter_models(rows)] == ["acme/big-1:free", "acme/small-2:free"]


def test_diff():
    old = [{"id": "a"}, {"id": "b"}]
    new = [{"id": "b"}, {"id": "c"}]
    d = core.diff_models(old, new)
    assert d["added"] == ["c"]
    assert d["removed"] == ["a"]
    assert d["kept"] == ["b"]


def test_chain_and_yaml():
    rows = core.parse_openrouter_models(load_sample())
    chain = core.build_chain(rows, limit=2)
    assert chain["models"][0] == "acme/big-1:free"
    yaml = core.chain_to_litellm_yaml(chain)
    assert "openrouter/acme/big-1:free" in yaml
    assert "os.environ/OPENROUTER_API_KEY" in yaml
    assert "sk-" not in yaml


def test_classify_http():
    assert core.classify_http(200) == "ok"
    assert core.classify_http(429) == "transient"
    assert core.classify_http(503) == "transient"
    assert core.classify_http(404) == "hard"
    assert core.classify_http(401) == "hard"


def test_curated_providers_have_sources():
    rows = core.load_curated_providers()
    assert len(rows) >= 5
    for r in rows:
        assert r["source"].startswith("https://")
        assert r["verified"] == "2026-10-22"


def test_cache_roundtrip():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        cache = Path(d) / "c.json"
        core.save_cache([{"id": "x"}], cache)
        assert core.load_cache(cache) == [{"id": "x"}]
        assert core.load_cache(Path(d) / "missing.json") == []
