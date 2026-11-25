"""Exercise three diagnostic physical outcome paths from saved telemetry.

This is a CPU test fixture. The resulting physical checks do not establish
actual C130864 Native capture or legal status.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def probe(attempt: Path, kind: str, output: Path) -> dict:
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("unknown diagnostic physical outcome")
    # This import is deliberately after the caller exports the ignored output
    # root. The test never imports the pipeline into runtime/ for output.
    if "SCENARIO_PIPELINE_OUTPUT_ROOT" not in os.environ:
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before import")
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import physical_result

    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    scratch = repo / ".runtime-work/c130864-physical-tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="physical-", dir=scratch) as temporary:
        root = Path(temporary)
        for name in ("config.json", "trace.jsonl", "video_frames.jsonl"):
            shutil.copyfile(attempt / name, root / name)
        cfg = json.loads((root / "config.json").read_text())
        cfg["physical_completion"] = {
            "criterion": "travel_progress",
            "minimum_progress_m": 0.25,
            "completion_goal_method": "diagnostic observed motion only; not roundabout entry or legal gap"
        }
        (root / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
        (root / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True
        }) + "\n")
        if kind in ("complete_motion", "incomplete_motion"):
            rows = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines() if line]
            first = rows[0]["position_m"]
            for index, row in enumerate(rows):
                point = [first[0] + (index if kind == "complete_motion" else 0),
                         first[1], first[2]]
                row["position_m"] = point
                row["position"] = {"x": point[0], "y": point[1], "z": point[2]}
                row["velocity_mps"] = [20 if kind == "complete_motion" else 0, 0, 0]
                row["speed_mps"] = 20 if kind == "complete_motion" else 0
                row["speed_mph"] = row["speed_mps"] * 2.2369362921
            (root / "trace.jsonl").write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
        elif kind == "missing_evidence":
            (root / "trace.jsonl").unlink()
        baseline = json.loads((attempt / "result.json").read_text())
        measured = physical_result(root, baseline)
        actual = measured["physical_checks"]["maneuver"]["status"]
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if actual != expected or measured["provenance_kind"] != "synthetic_fixture" or \
           measured["diagnostic_fixture"] is not True or \
           measured["maneuver_completed"] is not (expected == "met"):
            raise ValueError("diagnostic physical outcome differs: " + kind)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(measured, indent=2, allow_nan=False) + "\n")
        return {"case_id": measured["case_id"], "fixture_kind": kind,
                "maneuver_status": actual, "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(probe(args.attempt, args.kind, args.output)))


if __name__ == "__main__":
    main()
