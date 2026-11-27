"""Source-bound synthetic complete, incomplete and missing motion probes.

The Native event criterion is engineering evidence only. These fixture outcomes
never assert that a real rider completed a turn or exposed an arm to cameras.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent
SCRATCH = REPO / ".runtime-work/c229831-temp"
PIPELINE = REPO / "runtime/scenario_pipeline"


def write_rows(path, values):
    path.write_text("".join(json.dumps(value, separators=(",", ":")) + "\n"
                            for value in values))


def prove(case_id, kind, output):
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown physical fixture kind")
    if not case_id.startswith(FOLDER.name + "__probe_"):
        raise ValueError("Wrong exact case")
    root_env = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if root_env != SCRATCH.resolve():
        raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
    sys.path.insert(0, str(PIPELINE))
    from worker_exchange.native_output import physical_result
    manifest = json.loads((FOLDER / "execution-manifest.json").read_text())
    entry = next(e for e in manifest["cases"] if e["case_id"] == case_id)
    construction = json.loads((FOLDER / entry["construction"]).read_text())
    config = json.loads(next(f["content"] for f in construction["files"]
                             if f["path"] == "config.json"))
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix="physical-") as temporary:
        attempt = Path(temporary)
        (attempt / "config.json").write_text(json.dumps(config) + "\n")
        (attempt / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        mapping = [{"video_frame": frame, "carla_frame": frame + 1000,
                    "native_frame": frame + 1000, "time_s": frame / 20}
                   for frame in range(600)]
        write_rows(attempt / "video_frames.jsonl", mapping)
        if kind != "missing_evidence":
            trace = []
            for frame in range(600):
                # Route has an approach, curved heading transition and exit.
                yaw = -90 * max(0, min(1, (frame - 250) / 100))
                if kind == "incomplete_motion":
                    yaw = 0
                x = -40 + min(frame, 300) * .05
                y = -max(0, frame - 300) * .05
                trace.append({"frame": frame + 1000, "time_s": frame / 20,
                              "position_m": [x, y, .8], "heading_deg": yaw})
            write_rows(attempt / "trace.jsonl", trace)
        target = {"target": "selected_arm_pose_frames", "requested": 40,
                  "measured": 40, "method": "synthetic diagnostic source join",
                  "tolerance": 0, "matched": True,
                  "physical_cause_confirmed": False, "cause_evidence": ["rider_arm.jsonl"]}
        assessed = physical_result(attempt, {
            "case_id": case_id, "target_checks": [target],
            "physical_failure_flags": ["synthetic_fixture_only"]})
        status = assessed["physical_checks"]["maneuver"]["status"]
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if status != expected or assessed["maneuver_completed"] != (expected == "met"):
            raise ValueError("Physical outcome did not reflect source evidence")
        Path(output).write_text(json.dumps(assessed, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"case_id": case_id, "fixture_kind": kind,
                          "maneuver": status, "diagnostic_fixture": True,
                          "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    prove(args.case, args.kind, args.output)
