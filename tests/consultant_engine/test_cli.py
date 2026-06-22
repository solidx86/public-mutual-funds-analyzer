import json, subprocess, sys
from pathlib import Path

import pytest

from consultant_engine.cli import _latest_fundmaster


def _touch_fm(d: Path, name: str) -> None:
    (d / name).write_bytes(b"")


def test_latest_fundmaster_picks_newest_month_and_version(tmp_path):
    _touch_fm(tmp_path, "PublicMutual_FundMaster_Feb2026_v1.1.xlsx")
    _touch_fm(tmp_path, "PublicMutual_FundMaster_Apr2026_v1.7.xlsx")
    # v1.10 must beat v1.7 (integer compare, not lexical), same month
    _touch_fm(tmp_path, "PublicMutual_FundMaster_Apr2026_v1.10.xlsx")
    # a stray non-matching file must be ignored
    _touch_fm(tmp_path, "notes.xlsx")
    picked = _latest_fundmaster([tmp_path])
    assert Path(picked).name == "PublicMutual_FundMaster_Apr2026_v1.10.xlsx"


def test_latest_fundmaster_prefers_first_dir_with_matches(tmp_path):
    live = tmp_path / "live"
    examples = tmp_path / "examples"
    live.mkdir(); examples.mkdir()
    # live has an older book; examples has a newer one — live still wins (priority, not recency)
    _touch_fm(live, "PublicMutual_FundMaster_Feb2026_v1.1.xlsx")
    _touch_fm(examples, "PublicMutual_FundMaster_Apr2026_v1.7.xlsx")
    picked = _latest_fundmaster([live, examples])
    assert Path(picked).name == "PublicMutual_FundMaster_Feb2026_v1.1.xlsx"


def test_latest_fundmaster_skips_empty_dirs_then_falls_back(tmp_path):
    empty = tmp_path / "empty"
    examples = tmp_path / "examples"
    empty.mkdir(); examples.mkdir()
    _touch_fm(examples, "PublicMutual_FundMaster_Apr2026_v1.7.xlsx")
    picked = _latest_fundmaster([empty, tmp_path / "missing", examples])
    assert Path(picked).name == "PublicMutual_FundMaster_Apr2026_v1.7.xlsx"


def test_latest_fundmaster_raises_when_none_found(tmp_path):
    with pytest.raises(SystemExit):
        _latest_fundmaster([tmp_path])


def test_cli_runs_with_no_review(tmp_path, fundmaster_4fund):
    # Use fundmaster_4fund (not tiny_fundmaster): the real build_portfolio node
    # requires ≥2 equity funds + PeEMAS + PeCDF-A to pass invariants.
    prof = tmp_path / "p.json"
    prof.write_text(json.dumps({
        "risk_level": "Moderate", "shariah": False, "experience": "experienced",
        "upfront_capital_rm": 50000, "target_annual_return_pct": 5.0
    }))
    r = subprocess.run(
        [sys.executable, "-m", "consultant_engine",
         "--profile", str(prof), "--fundmaster", fundmaster_4fund,
         "--macro", "none", "--no-review", "-o", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    # A clean exit must have produced a real proposal carrying the version stamp.
    from consultant_engine import __version__
    produced = list(Path(tmp_path).glob("FundProposal_*.html"))
    assert produced, f"no FundProposal_*.html written to {tmp_path}; stdout={r.stdout}"
    text = produced[0].read_text(encoding="utf-8")
    assert f"fund-consultant v{__version__}" in text, "proposal missing version stamp"


def test_latest_fundmaster_default_search_dirs_resolve_a_real_workbook():
    # With no args, the resolver must find a real workbook via its production
    # search dirs: output/fundmasters/ (private symlink on dev installs) or, on a
    # public clone / CI where that symlink is absent, output/examples/fundmasters/.
    from consultant_engine.cli import _fm_sort_key
    picked = _latest_fundmaster()
    assert Path(picked).exists()
    assert _fm_sort_key(Path(picked).name) is not None


def _run_cli(*cli_args):
    return subprocess.run(
        [sys.executable, "-m", "consultant_engine", *cli_args],
        capture_output=True, text=True,
    )


def test_help_is_newcomer_oriented():
    # --help must exit 0 and explain the workflow, not just list bare flags.
    r = _run_cli("--help")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "Generate an HTML investment proposal" in out   # description
    assert "examples:" in out                              # copy-pasteable usage
    assert "profile JSON fields" in out                    # profile schema reference
    assert "--resume" in out and "--no-review" in out      # the review workflow


def test_version_flag_reports_package_version():
    from consultant_engine import __version__
    r = _run_cli("--version")
    assert r.returncode == 0, r.stderr
    assert __version__ in r.stdout


def test_thread_id_rejects_path_separators():
    import argparse, pytest
    from consultant_engine.cli import _thread_id
    args = argparse.Namespace(resume="../../etc/passwd", profile=None)
    with pytest.raises(SystemExit):
        _thread_id(args)


def test_missing_profile_without_resume_errors_cleanly():
    # No --profile and no --resume: argparse-style error (exit 2) + guidance,
    # not a Path(None) traceback.
    r = _run_cli()
    assert r.returncode == 2
    assert "--profile is required" in r.stderr
    assert "Traceback" not in r.stderr
