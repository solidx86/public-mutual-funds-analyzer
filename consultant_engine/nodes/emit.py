import re
from datetime import datetime
from pathlib import Path

import consultant_engine
from consultant_engine.state import ConsultantState


def _name_segment(client_name: str) -> str:
    """Build the filename's name segment from a client name.

    Strips spaces, punctuation, and the underscore while preserving every unicode
    word character (Python 3 ``\\w`` is unicode-aware for ``str``, so accented and
    CJK names survive), and falls back to the literal ``"generic"`` when nothing
    usable remains.
    """
    # \w keeps unicode letters/digits but also the underscore; strip the underscore
    # explicitly so it never leaks into a filename.
    segment = re.sub(r"[^\w]", "", client_name or "", flags=re.UNICODE).replace("_", "")
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
