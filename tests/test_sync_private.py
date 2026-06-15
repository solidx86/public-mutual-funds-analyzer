import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "sync-private.sh"


def test_script_exists_and_executable():
    assert SCRIPT.is_file(), "scripts/sync-private.sh must exist"
    assert SCRIPT.stat().st_mode & 0o111, "script must be executable"


def test_noop_when_no_private_mount(tmp_path):
    # Run from a scratch dir that has no output/fund_proposals mount.
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"expected clean no-op, got {result.returncode}: {result.stderr}"
    assert "skipping" in result.stdout.lower()
