"""Live macro agent (web-search producer) — fallback chain, cache TTL, cost, guards.

The agent is non-deterministic and network-bound, so every test injects a fake
``searcher`` and a fixed ``now`` — no real API calls. The contract under test is the
*resolution policy*: when to use the fixture, the cache, or a fresh search, and that
any failure degrades to the fixture rather than crashing the run.
"""
import json
from datetime import datetime, timedelta

import pytest

from consultant_engine.llm import estimate_cost_usd, web_search
from consultant_engine.macro import fetch_live_macro, load_fixture


_GOOD = ('[{"date":"2026-06-20","theme":"OPR","claim":"BNM held the OPR at 3.00%.",'
         '"source_url":"https://bnm.gov.my/x"}]')


def _searcher_ok(prompt, *, model="claude-sonnet-4-6"):
    return _GOOD, {"input_tokens": 1000, "output_tokens": 200,
                   "web_searches": 3, "cost_usd": 0.0360}


def _live_env(monkeypatch):
    """Disable the autouse FAKE_LLM and supply a dummy key so the live path runs."""
    monkeypatch.delenv("CONSULTANT_ENGINE_FAKE_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


def test_fake_mode_uses_fixture_without_searching(tmp_path):
    # autouse FAKE_LLM is on → fixture; the searcher must never be called.
    called = []
    ctx = fetch_live_macro(cache_path=tmp_path / "m.json",
                           searcher=lambda *a, **k: (called.append(1), ("[]", {}))[1])
    assert ctx.events == load_fixture().events
    assert not called


def test_no_api_key_uses_fixture(monkeypatch, tmp_path):
    monkeypatch.delenv("CONSULTANT_ENGINE_FAKE_LLM", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    called = []
    ctx = fetch_live_macro(cache_path=tmp_path / "m.json",
                           searcher=lambda *a, **k: (called.append(1), ("[]", {}))[1])
    assert ctx.events == load_fixture().events
    assert not called


def test_fresh_cache_skips_search(monkeypatch, tmp_path):
    _live_env(monkeypatch)
    now = datetime(2026, 6, 21, 12, 0, 0)
    cache = tmp_path / "m.json"
    cache.write_text(json.dumps({
        "fetched_at": (now - timedelta(hours=2)).isoformat(),
        "events": [{"date": "2026-06-20", "theme": "OPR",
                    "claim": "cached.", "source_url": "https://x"}],
    }))
    called = []
    ctx = fetch_live_macro(cache_path=cache, now=now,
                           searcher=lambda *a, **k: (called.append(1), (_GOOD, {}))[1])
    assert ctx.events[0].claim == "cached."
    assert not called  # cache < 24h → no search


def test_stale_cache_refetches_and_rewrites(monkeypatch, tmp_path):
    _live_env(monkeypatch)
    now = datetime(2026, 6, 21, 12, 0, 0)
    cache = tmp_path / "m.json"
    cache.write_text(json.dumps({
        "fetched_at": (now - timedelta(hours=30)).isoformat(),
        "events": [{"date": "2026-05-01", "theme": "OPR",
                    "claim": "stale.", "source_url": "https://x"}],
    }))
    ctx = fetch_live_macro(cache_path=cache, now=now, searcher=_searcher_ok)
    assert ctx.events[0].claim == "BNM held the OPR at 3.00%."   # fresh search wins
    written = json.loads(cache.read_text())
    assert written["fetched_at"] == now.isoformat()
    assert written["usage"]["web_searches"] == 3                # usage persisted for costing


def test_bad_json_falls_back_to_fixture(monkeypatch, tmp_path):
    _live_env(monkeypatch)
    ctx = fetch_live_macro(cache_path=tmp_path / "m.json",
                           searcher=lambda *a, **k: ("sorry, no data found", {}))
    assert ctx.events == load_fixture().events   # no crash, fixture fallback


def test_invalid_event_schema_falls_back(monkeypatch, tmp_path):
    _live_env(monkeypatch)
    bad = '[{"date":"2026-06-20","theme":"OPR","claim":"no url here"}]'  # missing source_url
    ctx = fetch_live_macro(cache_path=tmp_path / "m.json",
                           searcher=lambda *a, **k: (bad, {}))
    assert ctx.events == load_fixture().events


def test_estimate_cost_usd():
    # 1M in @ $3 + 1M out @ $15 + 1000 searches @ $10 = 28.00
    assert estimate_cost_usd(1_000_000, 1_000_000, 1000) == 28.0
    assert estimate_cost_usd(0, 0, 0) == 0.0


def test_web_search_refuses_fake_mode(monkeypatch):
    monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
    with pytest.raises(RuntimeError, match="FAKE_LLM"):
        web_search("hello")
