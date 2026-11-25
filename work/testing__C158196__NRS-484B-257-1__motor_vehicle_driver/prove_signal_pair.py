"""Diagnostic CLI proof for the frozen signal-governance comparison pair."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / ".runtime-work" / "c158196-signal-pair"
sys.path.insert(0, str(HERE / "tests"))
from test_nearest_view import write_attempt  # noqa: E402
from test_signal_exception import active_attempt  # noqa: E402


def run(left: Path, right: Path, output: Path, name: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(HERE / "saved_comparison.py"),
               "governing_signal_exception", str(left), str(right), str(output)]
    result = subprocess.run(command, cwd=ROOT,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                            capture_output=True, text=True, check=False)
    (HERE / name).write_text(
        (f"exit: {result.returncode}\n" + result.stdout + result.stderr).rstrip("\n") + "\n",
        encoding="utf-8")
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    left, right = OUT / "nearest_view_clear", OUT / "active_signal_exception"
    write_attempt(left, "nearest_view_clear",
                  policy="continue_after_clear_observation", minimum_speed=2.0)
    active_attempt(right)
    proof = OUT / "comparison.json"
    positive = run(left, right, proof, "cpu-signal-pair-positive.log")
    if positive.returncode:
        raise ValueError("frozen pair CLI positive failed")
    measured = json.loads(proof.read_text(encoding="utf-8"))
    if measured.get("comparison_id") != "governing_signal_exception":
        raise ValueError("wrong comparison identity")

    wrong = OUT / "nearest_view_continue"
    write_attempt(wrong, "nearest_view_continue",
                  policy="continue_through_observed_traffic", minimum_speed=2.0)
    wrong_case = run(wrong, right, OUT / "wrong-case.json", "cpu-signal-pair-wrong-case.log")
    if wrong_case.returncode == 0 or "saved case identity differs" not in wrong_case.stderr:
        raise ValueError("wrong frozen left case was accepted")

    source = right / "native" / "signal_state_readback.json"
    source.write_text("tampered\n", encoding="utf-8")
    stale_source = run(left, right, OUT / "stale-source.json", "cpu-signal-pair-stale-source.log")
    if stale_source.returncode == 0 or "source hash mismatch" not in stale_source.stderr:
        raise ValueError("stale signal source was accepted")
    print("diagnostic frozen pair positive, wrong-case and stale-source negatives passed")


if __name__ == "__main__":
    main()
