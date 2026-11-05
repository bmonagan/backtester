import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_top25_manifest_matches_source_inputs():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/freeze_top25_manifest.py")],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    assert "Verified docs/top-25-strict-backtest-manifest.json" in result.stdout
