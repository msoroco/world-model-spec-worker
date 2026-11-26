"""CPU source-join and missing-device proofs for explicit statutory actions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from saved_angle_activity import measure

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSIGNMENT = HERE.parent.name


def run(action, letter):
    if action not in ("stop", "stand") or letter not in "ab":
        raise ValueError("Unknown statutory action case")
    prefix = f"selected-{action}-{letter}"
    case = ASSIGNMENT + f"__selected_03f318de__{action}_condition_{letter}"
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work", prefix="c385967-activity-source-") as name:
        attempt = Path(name) / "attempt"
        command = [sys.executable, "-B", str(ROOT / "runtime.py"), "fixture",
                   "--recipe", str(HERE / f"{prefix}-fixture-recipe.json"),
                   "--output", str(attempt)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=900)
        if result.returncode:
            raise ValueError(result.stdout[-1000:] + result.stderr[-2500:])
        positive = measure(attempt, case, allow_fixture=True)
        if positive["frames"] != 600 or positive["longest_at_rest_run"] != 600:
            raise ValueError("Full source-bound at-rest window absent")
        negative = Path(name) / "negative"
        shutil.copytree(attempt, negative)
        (negative / "official_device.json").unlink()
        try:
            measure(negative, case, allow_fixture=True)
        except ValueError as exc:
            if "Missing required source: official_device.json" not in str(exc):
                raise
            error = str(exc)
        else:
            raise ValueError("Missing official-device source was accepted")
    (HERE / f"{prefix}-source-positive.json").write_text(json.dumps(positive, indent=2) + "\n")
    (HERE / f"{prefix}-source-negative.json").write_text(json.dumps({
        "case_id": case, "rejected": True, "error": error,
        "source_kind": "synthetic_cpu_fixture"}, indent=2) + "\n")
    return {"case_id": case, "positive": True, "missing_device_rejected": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("stop", "stand"), required=True)
    parser.add_argument("--condition", choices=("a", "b"), required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.action, args.condition), sort_keys=True))
