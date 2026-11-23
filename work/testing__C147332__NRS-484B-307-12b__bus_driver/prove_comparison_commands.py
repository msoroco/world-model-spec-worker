"""Exercise the two exact red-X comparison entrypoints and a reuse rejection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PAIRS = (("red_x_lateral_entry", "adjacent_travel", "lateral_entry"),
         ("red_x_in_lane_driving", "red_lane_stand", "red_lane_drive"))


def invoke(comparison_id: str, baseline: Path, changed: Path, output: Path):
    return subprocess.run(
        [sys.executable, str(ROOT / "independent/comparison_audit.py"),
         "--comparison-id", comparison_id, "--baseline-attempt", str(baseline),
         "--changed-attempt", str(changed), "--output", str(output), "--diagnostic"],
        capture_output=True, text=True, check=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    base = (ROOT.parents[1] / ".runtime-work").resolve()
    attempts, output = args.attempt_root.resolve(), args.output_root.resolve()
    if not attempts.is_relative_to(base) or not output.is_relative_to(base):
        raise ValueError("diagnostic paths must stay under .runtime-work")
    output.mkdir(parents=True, exist_ok=True)
    for comparison_id, left, right in PAIRS:
        receipt_path = output / (comparison_id + ".json")
        result = invoke(comparison_id, attempts / left, attempts / right, receipt_path)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        receipt = json.loads(receipt_path.read_text())
        if (receipt["comparison_id"] != comparison_id or
                receipt["baseline_case_id"] != ROOT.name + "__" + left or
                receipt["changed_case_id"] != ROOT.name + "__" + right or
                not receipt["diagnostic_fixture"] or receipt["physical_acceptance_claimed"]):
            raise AssertionError("exact comparison receipt differs")
        reuse = invoke(comparison_id, attempts / left, attempts / left,
                       output / (comparison_id + "-invalid.json"))
        if reuse.returncode == 0 or "reuses one original attempt" not in reuse.stderr:
            raise AssertionError("same attempt accepted")
        print(comparison_id + ": exact CLI and reuse negative passed", flush=True)


if __name__ == "__main__":
    main()
