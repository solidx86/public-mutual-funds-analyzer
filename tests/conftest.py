"""Shared fixtures: build an isolated pipeline workspace under tmp so test runs
never touch the repo's tracked outputs. Scripts derive all paths from their own
location, so copying the skill bundle into the workspace redirects every read
and write there."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "fund-screener-skill" / "scripts"


def make_workspace(dest: Path, mfr_data: dict, with_ath: bool = True) -> Path:
    """Lay out a minimal copy of the repo that the pipeline scripts can run in."""
    skill_dst = dest / "fund-screener-skill"
    skill_dst.mkdir(parents=True)
    shutil.copytree(SCRIPTS, skill_dst / "scripts")
    shutil.copy(REPO_ROOT / "fund-screener-skill" / "SKILL.md", skill_dst / "SKILL.md")

    # Pipeline scripts read/write cache files under data/cache and look up
    # funds_risk_level.xlsx under data/reference — mirror that layout here.
    cache_dir = dest / "data" / "cache"
    ref_dir = dest / "data" / "reference"
    cache_dir.mkdir(parents=True)
    ref_dir.mkdir(parents=True)

    ut_dir = dest / "unit-trust"
    ut_dir.mkdir()
    mfr_data = dict(mfr_data)
    mfr_data["base_dir"] = str(ut_dir)
    (cache_dir / "mfr_results.json").write_text(json.dumps(mfr_data))

    shutil.copy(REPO_ROOT / "data" / "reference" / "funds_risk_level.xlsx", ref_dir / "funds_risk_level.xlsx")
    if with_ath:
        shutil.copy(REPO_ROOT / "data" / "cache" / "ath_results.json", cache_dir / "ath_results.json")

    (dest / "output" / "fundmasters").mkdir(parents=True)
    return dest


def run_script(workspace: Path, script_name: str) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [sys.executable, str(workspace / "fund-screener-skill" / "scripts" / script_name)],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, f"{script_name} failed:\n{proc.stdout}\n{proc.stderr}"
    return proc


@pytest.fixture(scope="session")
def pipeline_workspace(tmp_path_factory):
    """Run the offline half of the pipeline (steps 3 and 4) once, from the
    tracked cached JSONs, exactly as a fresh clone would."""
    mfr_data = json.loads((REPO_ROOT / "data" / "cache" / "mfr_results.json").read_text())
    ws = make_workspace(tmp_path_factory.mktemp("pipeline"), mfr_data)
    run_script(ws, "build_sheet_data.py")
    run_script(ws, "build_xlsx.py")
    return ws


# ── consultant_engine (Track 0) fixtures ───────────────────────────────────
# These live in the root conftest rather than a tests/consultant_engine/conftest.py
# on purpose: that directory name collides with the production `consultant_engine`
# package (breaks pytest package import), and a second conftest.py would shadow the
# bare `from conftest import ...` that test_pipeline.py relies on. Root conftest
# fixtures are available to every test, including the consultant_engine suite.

def _row(ws, r, name, abbr, shariah, ftype, rl, status, walpha, **kw):
    ws.cell(r, 1, name); ws.cell(r, 2, abbr); ws.cell(r, 3, shariah)
    ws.cell(r, 4, ftype); ws.cell(r, 6, rl); ws.cell(r, 10, status); ws.cell(r, 14, walpha)
    for col, val in kw.items():
        ws.cell(r, int(col[1:]), val)         # pass c35=.. style overrides


@pytest.fixture
def tiny_fundmaster(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Master"
    ws.cell(3, 1, "Fund Name")                 # header marker on row 3
    _row(ws, 4, "Public Index Fund", "PIX", "No", "Equity", 3, "Qualified", 2.1,
         c72=-3.0, c73=20)
    _row(ws, 5, "PB Growth Fund", "PBGF", "No", "Equity", 4, "Qualified", 1.0)   # PB → excluded
    _row(ws, 6, "Public e-Cash Deposit", "PeCDF-B", "No", "Money Market", 1, "Qualified", 0.1)  # -B → excluded
    _row(ws, 7, "Public Wholesale", "PWSIF", "No", "Equity", 5, "Qualified", 3.0)  # wholesale → excluded
    _row(ws, 8, "Public e-Cash Deposit", "PeCDF-A", "No", "Money Market", 1, "Qualified", 0.1)
    p = tmp_path / "PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx"; wb.save(p)
    return str(p)
