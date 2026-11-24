"""Retain a synthetic positive and tampered-source CLI audit proof."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / ".runtime-work" / "c158196-saved-comparison"
sys.path.insert(0, str(HERE / "tests"))
from test_nearest_view import write_attempt  # noqa: E402


def main() -> None:
    left, right = OUT / "hold", OUT / "continue"
    write_attempt(left, "nearest_view_hold", policy="hold_for_observed_traffic", minimum_speed=0.1)
    write_attempt(right, "nearest_view_continue", policy="continue_through_observed_traffic", minimum_speed=2.0)
    command = [sys.executable, str(HERE / "saved_comparison.py"),
               "nearest_view_conflict_response", str(left), str(right), str(OUT / "audit.json")]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    good = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    (HERE / "cpu-comparison-positive.log").write_text(
        f"exit: {good.returncode}\n" + good.stdout + good.stderr, encoding="utf-8")
    if good.returncode:
        raise ValueError("positive saved comparison failed")
    (left / "native" / "view_raycast.json").write_text("tampered\n", encoding="utf-8")
    bad = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    (HERE / "cpu-comparison-negative.log").write_text(
        f"exit: {bad.returncode}\n" + bad.stdout + bad.stderr, encoding="utf-8")
    if bad.returncode == 0 or "view_raycast source hash mismatch" not in bad.stderr:
        raise ValueError("tampered source was not rejected")
    print("synthetic saved comparison positive and tampered-source rejection passed")


if __name__ == "__main__":
    main()
