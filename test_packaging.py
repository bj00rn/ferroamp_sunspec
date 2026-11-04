from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("arguments", [
    ["-m", "ferroamp_sunspec"],
    ["-m", "ferroamp_sunspec.server"],
    ["-m", "ferroamp_sunspec.mqtt"],
    ["ferroamp_sunspec.py"],
    ["server.py"],
    ["mqtt.py"],
])
def test_module_and_compatibility_entry_points(arguments):
    result = subprocess.run(
        [sys.executable, *arguments, "--help"],
        cwd=Path(__file__).parent, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--log-level" in result.stdout
