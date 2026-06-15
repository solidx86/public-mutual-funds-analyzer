"""Shared fixtures: build an isolated pipeline workspace under tmp so test runs
never touch the repo's tracked outputs. Scripts derive all paths from their own
location, so copying the skill bundle into the workspace redirects every read
and write there."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

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
