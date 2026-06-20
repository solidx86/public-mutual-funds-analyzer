import json, subprocess, sys
from pathlib import Path

def test_cli_runs_with_no_review(tmp_path, fundmaster_4fund):
    # Use fundmaster_4fund (not tiny_fundmaster): the real build_portfolio node
    # requires ≥2 equity funds + PeEMAS + PeCDF-A to pass invariants.
    prof = tmp_path / "p.json"
    prof.write_text(json.dumps({
        "risk_level": "Moderate", "shariah": False, "experience": "experienced",
        "upfront_capital_rm": 50000, "e_target": 5.0
    }))
    r = subprocess.run(
        [sys.executable, "-m", "consultant_engine",
         "--profile", str(prof), "--fundmaster", fundmaster_4fund,
         "--macro", "none", "--no-review", "-o", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
