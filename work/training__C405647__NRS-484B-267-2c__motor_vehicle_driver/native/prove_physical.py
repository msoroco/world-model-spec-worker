"""Exercise the saved ego-body progress criterion on diagnostic Native-shaped rows.

This tests the acquisition and assessment wiring. It does not determine whether
the driver was legally prepared to stop or whether a CARLA run will succeed.
"""

import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCRATCH = REPO / ".runtime-work" / "c405647-physical-proof"
if not Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve().is_relative_to(
        (REPO / ".runtime-work").resolve()):
    raise RuntimeError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
sys.path.insert(0, str(REPO / "runtime"))
from scenario_pipeline.worker_exchange.native_output import assess_physical


def write_lines(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def body(x):
    return [[x - 1, -2], [x + 1, -2], [x + 1, 0], [x - 1, 0]]


def run(kind):
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown diagnostic physical outcome")
    root = SCRATCH / kind
    root.mkdir(parents=True, exist_ok=True)
    cfg = {"law_id": "NRS-484B-267-2c", "cell_id": "C405647",
           "rate_hz": 20, "duration_s": 30,
           "physical_completion": {"criterion": "travel_progress",
                                   "motion_source": "motion_history.jsonl",
                                   "body_key": "ego_body_xy_m",
                                   "minimum_progress_m": 5,
                                   "completion_goal_method": "Original ego body progress during approach; engineering event only"}}
    (root / "config.json").write_text(json.dumps(cfg) + "\n")
    rows = [{"video_frame": i, "native_frame": 30 + i,
             "carla_frame": 30 + i, "time_s": i / 20} for i in range(3)]
    write_lines(root / "video_frames.jsonl", rows)
    write_lines(root / "trace.jsonl", [{"frame": r["carla_frame"]} for r in rows])
    motion = root / "motion_history.jsonl"
    if kind == "missing_evidence":
        motion.unlink(missing_ok=True)
    else:
        positions = [0, 3, 7] if kind == "complete_motion" else [0, 1, 2]
        write_lines(motion, [{"frame": r["carla_frame"], "time_s": r["time_s"],
                              "ego_body_xy_m": body(x)}
                             for r, x in zip(rows, positions)])
    result = assess_physical(root, cfg)
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    actual = result["physical_checks"]["maneuver"]["status"]
    if actual != expected or result["maneuver_completed"] != (kind == "complete_motion"):
        raise AssertionError(f"{kind}: expected {expected}, got {actual}")
    result.update(provenance_kind="synthetic_fixture", diagnostic_fixture=True,
                  physical_acceptance_claimed=False, legal_verdict_claimed=False)
    destination = HERE / "physical" / (kind + ".json")
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return {"kind": kind, "status": actual, "result": str(destination.relative_to(HERE.parent))}


if __name__ == "__main__":
    print(json.dumps({"fixtures": [run(kind) for kind in
          ("complete_motion", "incomplete_motion", "missing_evidence")]}))
