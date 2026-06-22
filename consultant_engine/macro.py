"""Macro context model + fixture loader.

Defines the validated MacroContext (dated events + exposure_gaps) consumed by the
macro_context node and the proposal narrative, plus ``load_fixture`` for the
bundled default when no live contract is supplied.
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from pydantic import BaseModel, ConfigDict

from consultant_engine.llm import FAKE_ENV, web_search


class MacroEvent(BaseModel):
    date: str
    theme: str
    claim: str
    source_url: str


class MacroContext(BaseModel):
    # extra="ignore" lets a live contract carry a routing-only "source" key without
    # tripping validation (it is not a model field).
    model_config = ConfigDict(extra="ignore")

    events: list[MacroEvent] = []
    # exposure_gaps is INJECTION-ONLY: the live web-search producer (fetch_live_macro)
    # returns events only and never populates gaps, so the build_portfolio I2 branch
    # that reads exposure_gaps is exercised solely via an injected macro contract.
    exposure_gaps: list[str] = []


def load_fixture() -> MacroContext:
    """Load the bundled default macro context from assets/macro_fixture.json."""
    p = Path(__file__).resolve().parent / "assets" / "macro_fixture.json"
    return MacroContext.model_validate(json.loads(p.read_text()))


# ── Live macro agent (web-search producer) ──────────────────────────────────────

DEFAULT_CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "macro_results.json"

_THEMES = ("Malaysia OPR / BNM policy, inflation, the ringgit (MYR/USD), the KLCI, "
           "US Fed policy, global equities, China / Asia, and AI / semiconductor capex")


def _macro_prompt(today: str) -> str:
    return (
        f"Today is {today}. Use web search to establish current macroeconomic conditions "
        f"relevant to a Malaysian unit-trust investor across these themes: {_THEMES}.\n\n"
        "Return ONLY a JSON array of 5-8 objects, each EXACTLY of the form:\n"
        '{"date":"YYYY-MM-DD","theme":"<short theme>","claim":"<one dated factual sentence>",'
        '"source_url":"<the URL you found it at>"}\n'
        "Every claim must come from a search result and carry its real source_url. "
        "Use the most recent dated data point per theme. Output the JSON array only — no prose."
    )


def _parse_events(text: str) -> list[dict]:
    """Extract the JSON event array from the agent's reply (tolerates ``` fences/prose)."""
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        raise ValueError("macro agent returned no JSON array")
    return json.loads(m.group(0))


def fetch_live_macro(*, model: str = "claude-sonnet-4-6", cache_path: Path | None = None,
                     ttl_hours: int = 24, now: datetime | None = None,
                     searcher=None) -> MacroContext:
    """Resolve macro context from a live web-search agent, with cache + safe fallback.

    Resolution order:
      1. FAKE_LLM set, or no ANTHROPIC_API_KEY  -> bundled fixture (keeps offline/CI safe).
      2. Cache younger than ``ttl_hours``        -> cached events (no re-query).
      3. Otherwise                               -> run the agent, validate, write cache.
    Any network / parse / validation error falls back to the fixture rather than failing
    the run — a proposal must never block on macro acquisition.

    ``now`` and ``searcher`` are injectable for tests (default: wall clock + llm.web_search).
    """
    cache_path = Path(cache_path) if cache_path else DEFAULT_CACHE
    now = now or datetime.now()
    searcher = searcher or web_search

    if os.environ.get(FAKE_ENV) or not os.environ.get("ANTHROPIC_API_KEY"):
        return load_fixture()

    # 2 — fresh cache?
    try:
        if cache_path.exists():
            cached = json.loads(cache_path.read_text())
            if now - datetime.fromisoformat(cached["fetched_at"]) < timedelta(hours=ttl_hours):
                print(f"  macro: cache hit ({cached.get('fetched_at')}, <{ttl_hours}h old) — $0.00 this run")
                return MacroContext(events=cached["events"])
    except Exception:
        pass  # corrupt/old-shape cache → refetch

    # 3 — live fetch
    try:
        text, usage = searcher(_macro_prompt(now.date().isoformat()), model=model)
        ctx = MacroContext(events=_parse_events(text))  # pydantic validates each event
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({
            "fetched_at": now.isoformat(),
            "model": model,
            "events": [e.model_dump() for e in ctx.events],
            "usage": usage,
        }, indent=2))
        print(f"  macro: live web search — {usage['input_tokens']} in + {usage['output_tokens']} out "
              f"tokens, {usage['web_searches']} searches ≈ ${usage['cost_usd']:.4f}")
        return ctx
    except Exception as e:
        print(f"  macro: live fetch failed ({type(e).__name__}: {e}); using fixture")
        return load_fixture()
