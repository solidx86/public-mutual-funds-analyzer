import json, subprocess, sys
from pathlib import Path

def test_cli_runs_with_no_review(tmp_path):
    prof = tmp_path / "p.json"
    prof.write_text(json.dumps({
        "risk_level": "Moderate", "shariah": False, "experience": "experienced",
        "upfront_capital_rm": 50000, "e_target": 5.0
    }))
    r = subprocess.run(
        [sys.executable, "-m", "consultant_engine",
         "--profile", str(prof), "--fundmaster", "x.xlsx",
         "--macro", "none", "--no-review", "-o", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
