import os

FAKE_ENV = "CONSULTANT_ENGINE_FAKE_LLM"
_FAKE_RESPONSE = "<!--FAKE_LLM-->"   # deterministic canned response used in fake mode


def complete(prompt: str, model: str = "claude-sonnet-4-6", system: str | None = None) -> str:
    """Return an LLM completion for `prompt`. When the env var CONSULTANT_ENGINE_FAKE_LLM
    is set (any non-empty value), returns a deterministic canned string WITHOUT importing
    or calling the Anthropic SDK and without needing an API key — so tests + CI stay offline."""
    if os.environ.get(FAKE_ENV):
        return _FAKE_RESPONSE
    # real path: import lazily so the fake path never needs the SDK/key
    import anthropic
    client = anthropic.Anthropic()
    kwargs = {"model": model, "max_tokens": 8000,
              "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    # concatenate text blocks
    return "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
