import os

FAKE_ENV = "CONSULTANT_ENGINE_FAKE_LLM"
_FAKE_RESPONSE = "<!--FAKE_LLM-->"   # deterministic canned response used in fake mode


def complete_with_usage(prompt: str, model: str = "claude-sonnet-4-6",
                        system: str | None = None) -> tuple[str, dict]:
    """Return ``(text, usage)`` for an LLM completion. ``usage`` =
    ``{input_tokens, output_tokens, web_searches, cost_usd}``. When
    CONSULTANT_ENGINE_FAKE_LLM is set, returns the canned response + zero usage
    WITHOUT importing or calling the Anthropic SDK — so tests + CI stay offline."""
    if os.environ.get(FAKE_ENV):
        return _FAKE_RESPONSE, {"input_tokens": 0, "output_tokens": 0,
                                "web_searches": 0, "cost_usd": 0.0}
    # real path: import lazily so the fake path never needs the SDK/key
    import anthropic
    client = anthropic.Anthropic()
    kwargs = {"model": model, "max_tokens": 8000,
              "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    usage = {"input_tokens": resp.usage.input_tokens,
             "output_tokens": resp.usage.output_tokens, "web_searches": 0,
             "cost_usd": estimate_cost_usd(resp.usage.input_tokens, resp.usage.output_tokens)}
    return text, usage


def complete(prompt: str, model: str = "claude-sonnet-4-6", system: str | None = None) -> str:
    """Text-only convenience wrapper over :func:`complete_with_usage`."""
    return complete_with_usage(prompt, model=model, system=system)[0]


# ── Real-LLM cost estimate (USD) ────────────────────────────────────────────────
# Default Sonnet-tier per-token prices + per-request web-search price. These are
# ESTIMATES for cost-visibility; refresh from https://www.anthropic.com/pricing.
_PRICE_PER_MTOK_IN = 3.0
_PRICE_PER_MTOK_OUT = 15.0
_PRICE_PER_1K_WEB_SEARCHES = 10.0


def estimate_cost_usd(input_tokens: int, output_tokens: int, web_searches: int = 0) -> float:
    """Rough USD cost for one call (default Sonnet pricing). Estimate only."""
    return round(
        input_tokens / 1e6 * _PRICE_PER_MTOK_IN
        + output_tokens / 1e6 * _PRICE_PER_MTOK_OUT
        + web_searches / 1000 * _PRICE_PER_1K_WEB_SEARCHES,
        4,
    )


def web_search(prompt: str, *, model: str = "claude-sonnet-4-6",
               system: str | None = None, max_searches: int = 5) -> tuple[str, dict]:
    """Real Anthropic call with the web_search server tool enabled.

    Returns ``(text, usage)`` where usage = ``{input_tokens, output_tokens,
    web_searches, cost_usd}``. Never runs in fake mode: the caller (fetch_live_macro)
    owns the FAKE_LLM / offline fallback to the fixture, so this guards against
    accidental use that would otherwise need a network + key."""
    if os.environ.get(FAKE_ENV):
        raise RuntimeError("web_search() must not be called in FAKE_LLM mode")
    import anthropic
    client = anthropic.Anthropic()
    kwargs = {
        "model": model,
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": "web_search_20250305", "name": "web_search",
                   "max_uses": max_searches}],
    }
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    server = getattr(resp.usage, "server_tool_use", None)
    searches = (getattr(server, "web_search_requests", 0) or 0) if server else 0
    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "web_searches": searches,
        "cost_usd": estimate_cost_usd(resp.usage.input_tokens, resp.usage.output_tokens, searches),
    }
    return text, usage
