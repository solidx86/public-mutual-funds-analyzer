# Client name + robust proposal filenaming — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the client's name a first-class optional profile field that renders on the proposal cover, drives a robust filename convention, and is verified post-generation.

**Architecture:** `client_name` enters via the profile JSON, is normalized once at the `load_profile` node (the input boundary), is rendered as a Python-owned (never LLM-authored) HTML-escaped "Prepared for" line on the cover, drives the `emit` filename, and is checked post-generation by a new pure rule in the validate layer. No new CLI surface.

**Tech Stack:** Python 3, LangGraph pipeline (`consultant_engine/`), pytest, `openpyxl`. Offline tests run under `CONSULTANT_ENGINE_FAKE_LLM=1` (an autouse fixture in `tests/conftest.py` already sets this for the whole `consultant_engine` suite).

## Global Constraints

- **Work in the worktree** `/Users/solid/Code/pmfa-client-name` on branch `client-name-filename`. Never edit `/Users/solid/Code/public-mutual-funds-analyzer` (another session is active there with uncommitted changes to `validate.py` / `rules/validation.py`). The shell cwd resets between commands — prefix every shell command with `cd /Users/solid/Code/pmfa-client-name &&`.
- **Named filename:** `FundProposal_<ClientName>_<RiskProfile>_<YYYY-MM-DD>_v<version>.html`
- **Generic filename:** `FundProposal_generic_<RiskProfile>_<YYYY-MM-DD>_v<version>.html`
- `<ClientName>` = client name with **every non-alphanumeric character removed**, case preserved; `generic` when that yields nothing.
- `<RiskProfile>` = `risk_level` with spaces removed (e.g. `ModeratelyAggressive`).
- `<YYYY-MM-DD>` = generation date (`datetime.now()`).
- `<version>` = parsed from the proposal's `fund-consultant v<version>` stamp, falling back to `consultant_engine.__version__`.
- `client_name` default is `""` (the generic sentinel). It is **HTML-escaped** wherever it reaches the DOM.
- The prepared-for block is **deterministic / Python-owned** — substituted before prose fill, never authored by the LLM.
- Follow existing code style; **Google-style docstrings** on every new/rewritten function.
- TDD: write the failing test first, watch it fail, implement minimally, watch it pass, commit.

---

### Task 1: `client_name` profile field + normalization + sample profiles

**Files:**
- Modify: `consultant_engine/state.py` (the `ClientProfile` TypedDict)
- Modify: `consultant_engine/nodes/load_profile.py`
- Modify: `data/profiles/aggressive.json`, `data/profiles/conservative.json`, `data/profiles/moderate.json`, `data/profiles/moderately_aggressive.json`
- Test: `tests/consultant_engine/test_load_profile.py`

**Interfaces:**
- Consumes: nothing (entry point).
- Produces: after `load_profile`, `state["client_profile"]["client_name"]` is always a present, normalized `str` (`""` when absent/blank). All later tasks rely on this guarantee.

- [ ] **Step 1: Write the failing tests**

Append to `tests/consultant_engine/test_load_profile.py`:

```python
import json
from pathlib import Path


def test_client_name_defaults_to_empty_when_absent():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000}})
    assert out["client_profile"]["client_name"] == ""


def test_client_name_trimmed_and_internal_whitespace_collapsed():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000, "client_name": "  Tan   Wei  Ming \n"}})
    assert out["client_profile"]["client_name"] == "Tan Wei Ming"


def test_client_name_whitespace_only_becomes_empty():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000, "client_name": "   \t  "}})
    assert out["client_profile"]["client_name"] == ""


def test_client_name_control_chars_stripped():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000, "client_name": "Tan\x00Wei"}})
    assert out["client_profile"]["client_name"] == "TanWei"


def test_client_name_length_capped_at_100():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000, "client_name": "A" * 200}})
    assert len(out["client_profile"]["client_name"]) == 100


def test_client_name_non_string_becomes_empty():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000, "client_name": 12345}})
    assert out["client_profile"]["client_name"] == ""


def test_shipped_profiles_declare_generic_client_name():
    prof_dir = Path(__file__).resolve().parents[2] / "data" / "profiles"
    files = list(prof_dir.glob("*.json"))
    assert files, "no sample profiles found"
    for p in files:
        prof = json.loads(p.read_text())
        assert prof.get("client_name", None) == "", f"{p.name} must declare client_name: ''"
        out = load_profile({"client_profile": prof})
        assert out["client_profile"]["client_name"] == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/solid/Code/pmfa-client-name && CONSULTANT_ENGINE_FAKE_LLM=1 python -m pytest tests/consultant_engine/test_load_profile.py -q`
Expected: FAIL — `KeyError: 'client_name'` (and the shipped-profiles assertion fails because the JSONs lack the field).

- [ ] **Step 3: Add the field to the `ClientProfile` TypedDict**

In `consultant_engine/state.py`, add `client_name` to `ClientProfile` (after `goals`):

```python
class ClientProfile(TypedDict):
    risk_level: str          # Conservative|Moderate|Moderately Aggressive|Aggressive
    shariah: Optional[bool]  # True | False | None (no preference)
    experience: Literal["new", "experienced"]
    upfront_capital_rm: float
    target_annual_return_pct: float          # percent p.a., e.g. 5.0
    goals: Optional[str]
    client_name: str         # optional; load_profile normalizes + defaults to "" (generic)
```

- [ ] **Step 4: Add normalization to `load_profile`**

In `consultant_engine/nodes/load_profile.py`, add `import re` at the top, a module-level helper, and one line inside `load_profile`:

```python
import re

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_MAX_NAME_LEN = 100


def _normalize_client_name(raw) -> str:
    """Normalize a raw client_name into a render- and filename-safe string.

    Collapses every run of whitespace (spaces, tabs, newlines) to a single
    space and trims the ends, strips residual control characters, and caps the
    length at ``_MAX_NAME_LEN``. A missing, non-string, or all-whitespace value
    normalizes to ``""`` — the generic sentinel.

    Args:
        raw: The raw ``client_name`` from the profile (any type).

    Returns:
        The cleaned name, or ``""`` when absent/blank/non-string.
    """
    if not isinstance(raw, str):
        return ""
    collapsed = " ".join(raw.split())          # trim + collapse all whitespace runs
    cleaned = _CONTROL_CHARS_RE.sub("", collapsed)
    return cleaned[:_MAX_NAME_LEN]
```

Then inside `load_profile`, after the `experience` setdefault line, add:

```python
    p["client_name"] = _normalize_client_name(p.get("client_name"))
```

- [ ] **Step 5: Add `client_name: ""` to all four sample profiles**

Add the line `"client_name": "",` as the first field of each JSON object in `data/profiles/aggressive.json`, `conservative.json`, `moderate.json`, `moderately_aggressive.json`. Example for `data/profiles/moderate.json`:

```json
{
  "client_name": "",
  "risk_level": "Moderate",
  "shariah": null,
  "experience": "new",
  "upfront_capital_rm": 100000,
  "target_annual_return_pct": 5.0,
  "goals": "Balanced growth toward retirement in about 15 years."
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd /Users/solid/Code/pmfa-client-name && CONSULTANT_ENGINE_FAKE_LLM=1 python -m pytest tests/consultant_engine/test_load_profile.py -q`
Expected: PASS (all tests, including pre-existing ones).

- [ ] **Step 7: Commit**

```bash
cd /Users/solid/Code/pmfa-client-name && git add consultant_engine/state.py consultant_engine/nodes/load_profile.py data/profiles/*.json tests/consultant_engine/test_load_profile.py && git commit -m "feat(consultant): optional client_name profile field, normalized at load_profile

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Render the "Prepared for" line on the cover

**Files:**
- Modify: `consultant_engine/assets/proposal_skeleton.html` (insert marker after the cover subtitle, line 34)
- Modify: `consultant_engine/nodes/generate_proposal.py` (add `import html`; substitute the block in the cover-facts area)
- Modify: `consultant_engine/assets/design_system.css` (add `.cover-prepared-for`, after line 162)
- Test: `tests/consultant_engine/test_generate_proposal.py`

**Interfaces:**
- Consumes: `state["client_profile"]["client_name"]` (Task 1).
- Produces: when named, the rendered HTML contains the literal `<div class="cover-prepared-for">Prepared for <strong>{html.escape(name)}</strong></div>`; when generic, no `cover-prepared-for` substring appears. Task 4's `check_prepared_for` depends on this exact format.

- [ ] **Step 1: Write the failing tests**

Append to `tests/consultant_engine/test_generate_proposal.py`:

```python
def test_prepared_for_renders_escaped_when_named(monkeypatch):
    monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
    s = _state()
    s["client_profile"]["client_name"] = "Tan <b>Wei</b> Ming"
    html_out = generate_proposal(s)["proposal_html"]
    assert 'class="cover-prepared-for"' in html_out
    assert "Prepared for <strong>Tan &lt;b&gt;Wei&lt;/b&gt; Ming</strong>" in html_out
    assert "<!--slot:cover.prepared_for_block-->" not in html_out


def test_prepared_for_absent_when_generic(monkeypatch):
    monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
    html_out = generate_proposal(_state())["proposal_html"]   # _state() has no client_name
    assert "cover-prepared-for" not in html_out
    assert "Prepared for <strong>" not in html_out
    assert "<!--slot:cover.prepared_for_block-->" not in html_out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/solid/Code/pmfa-client-name && CONSULTANT_ENGINE_FAKE_LLM=1 python -m pytest tests/consultant_engine/test_generate_proposal.py -k prepared_for -q`
Expected: FAIL — `test_prepared_for_renders_escaped_when_named` fails (no `cover-prepared-for` in output).

- [ ] **Step 3: Insert the marker in the skeleton**

In `consultant_engine/assets/proposal_skeleton.html`, between the `cover-subtitle` div (line 34) and the `cover-meta-grid` div (line 35), add the marker on its own line:

```html
    <div class="cover-subtitle"><!--slot:cover.subtitle--></div>
    <!--slot:cover.prepared_for_block-->
    <div class="cover-meta-grid">
```

- [ ] **Step 4: Substitute the block in `generate_proposal`**

In `consultant_engine/nodes/generate_proposal.py`, add `import html` to the imports (near `import os`, `import re`). Then, inside `generate_proposal`, in the cover-facts area immediately after the `for _marker, _val in (...)` cover-date loop (the block ending `skeleton = skeleton.replace(_marker, _val)` around line 783) and before the `_profile_facts` loop, add:

```python
    # Cover "Prepared for" line is Python-owned (never LLM): rendered from the
    # normalized, HTML-escaped client_name. A blank/generic name collapses the
    # marker to nothing so no empty block is emitted.
    _client_name = state["client_profile"].get("client_name", "").strip()
    _prepared_for = (
        f'<div class="cover-prepared-for">Prepared for '
        f"<strong>{html.escape(_client_name)}</strong></div>"
        if _client_name
        else ""
    )
    skeleton = skeleton.replace("<!--slot:cover.prepared_for_block-->", _prepared_for)
```

- [ ] **Step 5: Add the CSS rule**

In `consultant_engine/assets/design_system.css`, after the `.cover-subtitle { ... }` block (ends line 162), add:

```css
.cover-prepared-for {
  font-size: 15px;
  color: rgba(255,255,255,0.85);
  margin-top: -32px;   /* tuck beneath the subtitle's 48px gap */
  margin-bottom: 40px;
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd /Users/solid/Code/pmfa-client-name && CONSULTANT_ENGINE_FAKE_LLM=1 python -m pytest tests/consultant_engine/test_generate_proposal.py -q`
Expected: PASS — the new tests and all pre-existing ones (including `test_no_prose_slot_markers_remain`, which still holds because the marker is substituted).

- [ ] **Step 7: Commit**

```bash
cd /Users/solid/Code/pmfa-client-name && git add consultant_engine/assets/proposal_skeleton.html consultant_engine/nodes/generate_proposal.py consultant_engine/assets/design_system.css tests/consultant_engine/test_generate_proposal.py && git commit -m "feat(consultant): render Python-owned 'Prepared for' cover line

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Rewrite `emit` for the new filename convention

**Files:**
- Modify: `consultant_engine/nodes/emit.py` (full rewrite of the filename logic)
- Test: `tests/consultant_engine/test_emit.py` (replace existing tests)

**Interfaces:**
- Consumes: `state["proposal_html"]`, `state["client_profile"]["client_name"]`, `state["client_profile"]["risk_level"]`, `state.get("output_dir")`. (No longer reads `fundmaster_path`.)
- Produces: `{"output_path": str}` named per the Global Constraints.

- [ ] **Step 1: Replace the test file**

Overwrite `tests/consultant_engine/test_emit.py` with:

```python
import re
from pathlib import Path

from consultant_engine.nodes.emit import emit

SKILL_VERSION = "1.27"  # extracted from the proposal_html stamp
SAMPLE = ('<html><body><div>fund-consultant v' + SKILL_VERSION + '</div>'
          '<h4>AI-Generated Document</h4></body></html>')


def test_emit_generic_when_no_name(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Moderate"},
             "output_dir": str(tmp_path)}
    name = Path(emit(state)["output_path"]).name
    assert re.fullmatch(
        r"FundProposal_generic_Moderate_\d{4}-\d{2}-\d{2}_v1\.27\.html", name), name


def test_emit_full_name_spaces_removed(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Aggressive", "client_name": "Tan Wei Ming"},
             "output_dir": str(tmp_path)}
    name = Path(emit(state)["output_path"]).name
    assert re.fullmatch(
        r"FundProposal_TanWeiMing_Aggressive_\d{4}-\d{2}-\d{2}_v1\.27\.html", name), name


def test_emit_punctuation_only_name_falls_back_to_generic(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Moderate", "client_name": "!!!"},
             "output_dir": str(tmp_path)}
    name = Path(emit(state)["output_path"]).name
    assert name.startswith("FundProposal_generic_Moderate_"), name


def test_emit_risk_spaces_removed(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Moderately Aggressive", "client_name": ""},
             "output_dir": str(tmp_path)}
    name = Path(emit(state)["output_path"]).name
    assert "_ModeratelyAggressive_" in name, name


def test_emit_writes_content_and_version_suffix(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Moderate"},
             "output_dir": str(tmp_path)}
    p = emit(state)["output_path"]
    assert p.endswith("_v1.27.html")
    text = open(p).read()
    assert "AI-Generated Document" in text
    assert "fund-consultant v1.27" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/solid/Code/pmfa-client-name && CONSULTANT_ENGINE_FAKE_LLM=1 python -m pytest tests/consultant_engine/test_emit.py -q`
Expected: FAIL — current `emit` produces `FundProposal_Moderate_Unknown_v1.27.html` (old order, FundMaster-derived date), so the new-format regexes don't match.

- [ ] **Step 3: Rewrite `emit.py`**

Overwrite `consultant_engine/nodes/emit.py` with:

```python
import re
from datetime import datetime
from pathlib import Path

import consultant_engine
from consultant_engine.state import ConsultantState


def _name_segment(client_name: str) -> str:
    """Build the filename's name segment from a client name.

    Strips every non-alphanumeric character (spaces, punctuation) while
    preserving case, and falls back to the literal ``"generic"`` when nothing
    usable remains.

    Args:
        client_name: The (already normalized) client name, possibly ``""``.

    Returns:
        The alphanumeric name segment, or ``"generic"``.
    """
    segment = re.sub(r"[^A-Za-z0-9]", "", client_name or "")
    return segment or "generic"


def emit(state: ConsultantState) -> dict:
    """Write the generated proposal HTML to a version-stamped file.

    Filename: ``FundProposal_<NameOrGeneric>_<Risk>_<YYYY-MM-DD>_v<version>.html``

    Where:
        NameOrGeneric: ``client_name`` with non-alphanumerics stripped (case
            preserved), or ``generic`` when no usable name is present.
        Risk: the client's ``risk_level`` with spaces removed.
        YYYY-MM-DD: the generation date (today).
        version: parsed from the proposal's ``fund-consultant v<version>`` stamp,
            falling back to ``consultant_engine.__version__``.

    Args:
        state: Consultant state; reads ``proposal_html``, ``client_profile``
            (``client_name``, ``risk_level``), and optional ``output_dir``
            (defaults to ``output/fund_proposals``).

    Returns:
        ``{"output_path": str}`` — the path the proposal was written to.
    """
    html_text = state["proposal_html"]
    client_profile = state["client_profile"]
    output_dir = Path(state.get("output_dir", "output/fund_proposals"))

    # Version from the HTML stamp "fund-consultant v<version>", else package version.
    version_match = re.search(r"fund-consultant v([\d.]+)", html_text)
    version = version_match.group(1) if version_match else consultant_engine.__version__

    name_seg = _name_segment(client_profile.get("client_name", ""))
    risk = client_profile["risk_level"].replace(" ", "")
    date_seg = datetime.now().strftime("%Y-%m-%d")

    filename = f"FundProposal_{name_seg}_{risk}_{date_seg}_v{version}.html"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    output_path.write_text(html_text, encoding="utf-8")

    return {"output_path": str(output_path)}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/solid/Code/pmfa-client-name && CONSULTANT_ENGINE_FAKE_LLM=1 python -m pytest tests/consultant_engine/test_emit.py -q`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/solid/Code/pmfa-client-name && git add consultant_engine/nodes/emit.py tests/consultant_engine/test_emit.py && git commit -m "feat(consultant): robust proposal filename (name|generic, gen-date)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Post-generation `check_prepared_for` conformance rule

**Files:**
- Modify: `consultant_engine/rules/validation.py` (add `check_prepared_for`; add `client_name` param to `validate_html`)
- Modify: `consultant_engine/nodes/validate.py` (thread `client_name` through)
- Test: `tests/consultant_engine/test_validation_rules.py`, `tests/consultant_engine/test_validate_node.py`

**Interfaces:**
- Consumes: rendered HTML from Task 2 (exact `Prepared for <strong>{escaped}</strong>` + `class="cover-prepared-for"` format); `client_name` from Task 1.
- Produces: `check_prepared_for(html_text, client_name="") -> list[dict]` with codes `prepared_for_missing` / `prepared_for_unexpected`; `validate_html(html_text, version, wb_index, client_name="")` now includes this check.

- [ ] **Step 1: Write the failing tests**

Append to `tests/consultant_engine/test_validation_rules.py`:

```python
from consultant_engine.rules.validation import check_prepared_for

_NAMED_BLOCK = ('<div class="cover-prepared-for">Prepared for '
                '<strong>Tan Wei Ming</strong></div>')


def test_prepared_for_named_present_is_clean():
    assert check_prepared_for(_NAMED_BLOCK, "Tan Wei Ming") == []


def test_prepared_for_named_missing_flags():
    v = check_prepared_for("<div>no prepared-for here</div>", "Tan Wei Ming")
    assert len(v) == 1 and v[0]["code"] == "prepared_for_missing"


def test_prepared_for_escaped_name_matches():
    safe = ('<div class="cover-prepared-for">Prepared for '
            "<strong>A &amp; B</strong></div>")
    assert check_prepared_for(safe, "A & B") == []


def test_prepared_for_generic_no_block_is_clean():
    assert check_prepared_for("<div class='cover'>nothing</div>", "") == []


def test_prepared_for_generic_leaked_block_flags():
    v = check_prepared_for(_NAMED_BLOCK, "")
    assert len(v) == 1 and v[0]["code"] == "prepared_for_unexpected"
```

Append to `tests/consultant_engine/test_validate_node.py`:

```python
def test_named_client_validates_clean(fundmaster_4fund):
    s = {"client_profile": {"risk_level": "Moderate", "shariah": False,
                            "client_name": "Tan Wei Ming"},
         "fundmaster_path": fundmaster_4fund, "macro_context": {"source": "fixture"}}
    for step in (load_profile, load_funds, filter_universe, score_cfs,
                 macro_context, build_portfolio, generate_proposal):
        s.update(step(s))
    assert 'class="cover-prepared-for"' in s["proposal_html"]
    out = validate(s)
    assert out["violations"] == [], out["violations"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/solid/Code/pmfa-client-name && CONSULTANT_ENGINE_FAKE_LLM=1 python -m pytest tests/consultant_engine/test_validation_rules.py -k prepared_for tests/consultant_engine/test_validate_node.py::test_named_client_validates_clean -q`
Expected: FAIL — `ImportError: cannot import name 'check_prepared_for'`.

- [ ] **Step 3: Add `check_prepared_for` to the rules module**

In `consultant_engine/rules/validation.py`, add this function just before the `# ── Composite runner ──` divider (before `validate_html`). The module already imports `html as _html`:

```python
def check_prepared_for(html_text: str, client_name: str = "") -> list[dict[str, str]]:
    """Verify the cover's 'Prepared for' line matches the client profile.

    A named profile must render the escaped name inside a ``cover-prepared-for``
    block; a generic profile (empty name) must not leak such a block. The block
    is Python-owned, so a violation here signals a structural fill bug — a
    fail-loud regression guard, not an LLM-repairable prose miss (mirrors
    ``check_unfilled_slots``).

    Args:
        html_text: The rendered proposal HTML.
        client_name: The normalized client name (``""`` = generic).

    Returns:
        A list with at most one violation:
          * ``prepared_for_missing`` — named, but the escaped name's block is absent.
          * ``prepared_for_unexpected`` — generic, but a prepared-for block leaked.
    """
    name = (client_name or "").strip()
    has_block = 'class="cover-prepared-for"' in html_text
    if name:
        expected = f"Prepared for <strong>{_html.escape(name)}</strong>"
        if expected not in html_text:
            return [{"code": "prepared_for_missing",
                     "msg": f"cover 'Prepared for {name}' line missing or mismatched"}]
        return []
    if has_block:
        return [{"code": "prepared_for_unexpected",
                 "msg": "generic proposal leaked a 'Prepared for' block"}]
    return []
```

- [ ] **Step 4: Thread `client_name` through `validate_html`**

In `consultant_engine/rules/validation.py`, change the `validate_html` signature and add the new check to the returned concatenation:

```python
def validate_html(
    html_text: str,
    version: str,
    wb_index: dict[str, dict[str, Any]],
    client_name: str = "",
) -> list[dict[str, str]]:
    """Run all validation rules and return the concatenated list of violations.

    Args:
        html_text: The rendered proposal HTML.
        version: The expected version stamp.
        wb_index: The FundMaster workbook index (see ``workbook_index``).
        client_name: The normalized client name for the prepared-for check
            (``""`` = generic). Optional so existing callers keep working.

    Returns:
        ``[]`` for a clean proposal, else the list of violation dicts.
    """
    return (
        check_sections(html_text)
        + check_version_and_disclosure(html_text, version)
        + check_cfs_consistency(html_text)
        + check_perf_consistency(html_text)
        + check_exposure_consistency(html_text)
        + check_summary_consistency(html_text)
        + check_funds_in_workbook(html_text, wb_index)
        + check_alpha_warning(html_text, wb_index)
        + check_retail_eligibility(html_text, wb_index)
        + check_unfilled_slots(html_text)
        + check_prepared_for(html_text, client_name)
    )
```

- [ ] **Step 5: Thread `client_name` through the `validate` node**

Overwrite `consultant_engine/nodes/validate.py` with:

```python
from consultant_engine.state import ConsultantState
from consultant_engine.rules.validation import validate_html, workbook_index
from consultant_engine import __version__


def validate(state: ConsultantState) -> dict:
    """validate node: check the drafted HTML against the locked template + workbook.

    Reads ``proposal_html``, ``fundmaster_path``, and the profile's
    ``client_name`` (for the cover prepared-for check). Returns
    ``{"violations": [...]}`` — empty when the proposal conforms.

    Args:
        state: The consultant state.

    Returns:
        ``{"violations": list[dict]}``.
    """
    idx = workbook_index(state["fundmaster_path"])
    client_name = state["client_profile"].get("client_name", "")
    violations = validate_html(state["proposal_html"], __version__, idx, client_name)
    return {"violations": violations}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd /Users/solid/Code/pmfa-client-name && CONSULTANT_ENGINE_FAKE_LLM=1 python -m pytest tests/consultant_engine/test_validation_rules.py tests/consultant_engine/test_validate_node.py -q`
Expected: PASS (new and pre-existing tests, including `test_generated_proposal_validates_clean`, which stays clean because the generic pipeline emits no block).

- [ ] **Step 7: Commit**

```bash
cd /Users/solid/Code/pmfa-client-name && git add consultant_engine/rules/validation.py consultant_engine/nodes/validate.py tests/consultant_engine/test_validation_rules.py tests/consultant_engine/test_validate_node.py && git commit -m "feat(consultant): check_prepared_for post-generation conformance rule

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Rename tracked examples + fix stale documentation

**Files:**
- Rename: the 3 files under `output/examples/fund_proposals/`
- Modify: `CLAUDE.md` (Outputs & versioning naming line)
- Verify: `tests/test_proposal_validation.py` (legacy eval, no edit expected)

**Interfaces:**
- Consumes: nothing in code; the legacy eval discovers proposals by glob and resolves each workbook from the cover "Data Source" cell, so renames are safe.
- Produces: example filenames matching the new generic convention.

- [ ] **Step 1: Rename the three examples with `git mv`**

```bash
cd /Users/solid/Code/pmfa-client-name && \
git mv output/examples/fund_proposals/FundProposal_Aggressive_Jun2026_v0.1.0.html \
       output/examples/fund_proposals/FundProposal_generic_Aggressive_2026-06-12_v0.1.0.html && \
git mv output/examples/fund_proposals/FundProposal_Moderate_Jun2026_v0.1.0.html \
       output/examples/fund_proposals/FundProposal_generic_Moderate_2026-06-12_v0.1.0.html && \
git mv output/examples/fund_proposals/FundProposal_ModeratelyAggressive_Jun2026_v0.1.0.html \
       output/examples/fund_proposals/FundProposal_generic_ModeratelyAggressive_2026-06-12_v0.1.0.html
```

(The `2026-06-12` segment matches each file's internal `Prepared 12 Jun 2026` date. The files are generic — they correctly contain no prepared-for line.)

- [ ] **Step 2: Verify the legacy eval still passes against the renamed examples**

Run: `cd /Users/solid/Code/pmfa-client-name && python -m pytest tests/test_proposal_validation.py -q`
Expected: PASS — discovery is glob + cover-cell based; the only filename assertion (`endswith("_v0.1.0.html")`) still holds; `KNOWN_*` pin sets stay empty.

- [ ] **Step 3: Update the stale naming line in `CLAUDE.md`**

In `CLAUDE.md`, under *Outputs & versioning*, replace:

```markdown
- `output/fund_proposals/FundProposal_<RiskProfile>_<MonYYYY>[_<ClientName>]_v<skill-version>.html` — consultant output
```

with:

```markdown
- `output/fund_proposals/FundProposal_<ClientName|generic>_<RiskProfile>_<YYYY-MM-DD>_v<consultant-version>.html` — consultant output. `<ClientName>` is the client name with non-alphanumerics removed (case preserved), or the literal `generic` when no name is given; `<YYYY-MM-DD>` is the generation date.
```

- [ ] **Step 4: Commit**

```bash
cd /Users/solid/Code/pmfa-client-name && git add -A output/examples/fund_proposals CLAUDE.md && git commit -m "docs(consultant): rename examples to new convention + fix stale naming doc

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Full-suite verification

**Files:** none (verification only).

**Interfaces:** Consumes everything above; produces a green test suite.

- [ ] **Step 1: Run the entire consultant_engine suite**

Run: `cd /Users/solid/Code/pmfa-client-name && CONSULTANT_ENGINE_FAKE_LLM=1 python -m pytest tests/consultant_engine -q`
Expected: PASS (no failures, no errors).

- [ ] **Step 2: Run the eval + pipeline suites**

Run: `cd /Users/solid/Code/pmfa-client-name && python -m pytest tests/test_proposal_validation.py tests/test_pipeline.py -q`
Expected: PASS.

- [ ] **Step 3: Smoke-test a named run end-to-end (offline)**

```bash
cd /Users/solid/Code/pmfa-client-name && \
printf '{"client_name":"Tan Wei Ming","risk_level":"Moderate","shariah":null,"experience":"new","upfront_capital_rm":100000,"target_annual_return_pct":5.0,"goals":"smoke test"}' > /tmp/named_profile.json && \
CONSULTANT_ENGINE_FAKE_LLM=1 python -m consultant_engine --profile /tmp/named_profile.json --fundmaster output/examples/fundmasters/PublicMutual_FundMaster_Apr2026_v1.7.xlsx --no-review -o /tmp/named_out
```
Expected: prints `Done. Proposal written to /tmp/named_out/FundProposal_TanWeiMing_Moderate_<today>_v<ver>.html`. Confirm the file contains `class="cover-prepared-for"` and `Prepared for <strong>Tan Wei Ming</strong>`.

- [ ] **Step 4: Final status check**

Run: `cd /Users/solid/Code/pmfa-client-name && git status --short && git log --oneline -7`
Expected: clean working tree; commits for Tasks 1–5 plus the earlier spec commit on `client-name-filename`.

---

## Notes for the implementer

- **Merge coordination:** the other active session is editing `consultant_engine/nodes/validate.py` and `consultant_engine/rules/validation.py` on `track0-headless-consultant-engine-spec`. Tasks 4 touches both. Expect conflicts when these branches converge; resolve by keeping both their changes and the `check_prepared_for` addition / `validate_html` `client_name` kwarg.
- The spec lives at `docs/superpowers/specs/2026-06-22-client-name-and-filename-design.md` (+ `.html` companion), already committed on this branch.
