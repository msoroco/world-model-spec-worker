"""Synthetic, source-bound physical outcome probes for C150041.

These probes exercise the saved geometry measurement and completion decision.
They do not represent CARLA motion or establish legal acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from parking_finalizer import finalize
from parking_measurement import unit
from parking_pose import REQUESTS, body


ROOT = Path(__file__).resolve().parent
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scene_for(suffix):
    construction = json.loads((ROOT / "diagnostic" / suffix /
                               "construction-delivery.json").read_text())
    scene = json.loads(next(item["content"] for item in construction["files"]
                            if item["path"] == "scene.json"))
    if scene["case_id"] != ROOT.name + "__" + suffix:
        raise ValueError("physical probe scene identity differs")
    return scene


def history_for(scene, kind):
    if kind not in KINDS or kind == "missing_evidence":
        raise ValueError("motion history kind required")
    start = scene["spawn_center_xy_m"]
    target = scene["target_pose"]["target_center_xy_m"]
    initial = unit(scene["spawn_forward_xy"])
    final = unit(scene["target_pose"]["target_forward_xy"])
    fraction = 1.0 if kind == "complete_motion" else 0.5
    rows = []
    previous = start
    for index in range(85):
        progress = min(index / 80, 1.0) * fraction
        center = [start[axis] + progress * (target[axis] - start[axis])
                  for axis in (0, 1)]
        turn = min(max((index - 70) / 10, 0.0), 1.0) * fraction
        heading = unit([initial[axis] * (1 - turn) + final[axis] * turn
                        for axis in (0, 1)])
        speed = 0.0 if index >= 81 else math.dist(center, previous) * 20
        rows.append({"frame": index + 1, "time_s": round(index / 20, 5),
                     "body_vertices_xy_m": body(center, heading, length_m=4.5,
                                                  width_m=2.0),
                     "vehicle_forward_xy": list(heading),
                     "speed_m_s": speed,
                     "control": {"throttle": 0.35 if index < 80 else 0.0,
                                 "steer": 0.0, "brake": 1.0 if index >= 80 else 0.0}})
        previous = center
    return rows


def evaluate(suffix, kind, history_path):
    if suffix not in REQUESTS or kind not in KINDS:
        raise ValueError("unknown physical probe identity")
    folder = ROOT / "diagnostic" / suffix
    scene = scene_for(suffix)
    packet = folder / "reviewed-context.json"
    sources = {"reviewed-context.json": sha(packet)}
    if kind == "missing_evidence":
        if history_path.exists():
            raise ValueError("missing-evidence probe retained original history")
        try:
            finalize(packet, folder, suffix, history_path, "0" * 64)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("missing original history was accepted")
        return result_for(scene, "unverified", sources, {},
                          "source-bound finalizer rejected absent original history")
    sources["parking-history.jsonl"] = sha(history_path)
    measured = finalize(packet, folder, suffix, history_path,
                        sources["parking-history.jsonl"])
    first, last = measured["observations"][0], measured["observations"][-1]
    if len(measured["observations"]) != 85 or not measured["stationary_intervals"]:
        raise ValueError("physical probe lacks complete original frame and hold history")
    if [row["frame"] for row in measured["observations"]] != list(range(1, 86)):
        raise ValueError("physical probe frame sequence differs")
    target = scene["target_pose"]["target_center_xy_m"]
    approach_m = math.dist(first["body_center_xy_m"], last["body_center_xy_m"])
    target_error_m = math.dist(last["body_center_xy_m"], target)
    requested_m = math.dist(scene["spawn_center_xy_m"], target)
    hold = measured["stationary_intervals"][-1]
    target_heading_deg = (scene["target_pose"]["engineering_angle_request_deg"]
                          if scene["target_pose"]["orientation_request"] == "angled"
                          else (0 if scene["target_pose"]["heading_request"] == "lawful"
                                else 180))
    complete = (approach_m >= requested_m - 0.25 and target_error_m <= 0.25 and
                last["body_corners_inside_roadway"] == 4 and
                hold["last_frame"] == 85 and hold["duration_s"] >= 0.1 and
                (last["parallel_deviation_deg"] <= 3 if
                 scene["target_pose"]["orientation_request"] == "parallel" else
                 last["parallel_deviation_deg"] >= 10) and
                abs(last["lawful_heading_deviation_deg"] - target_heading_deg) <= 3)
    observed = {"approach_m": approach_m, "requested_approach_m": requested_m,
                "target_error_m": target_error_m,
                "stationary_hold_s": hold["duration_s"],
                "final_body_corners_inside_roadway":
                    last["body_corners_inside_roadway"],
                "final_parallel_deviation_deg": last["parallel_deviation_deg"],
                "final_lawful_heading_deviation_deg":
                    last["lawful_heading_deviation_deg"]}
    expected = kind == "complete_motion"
    if complete != expected:
        raise ValueError("measured physical outcome differs from probe")
    return result_for(scene, "met" if complete else "not_met", sources,
                      observed, "source-hashed 20 Hz full-body approach and stationary-hold measurement")


def result_for(scene, status, sources, observed, method):
    return {"case_id": scene["case_id"], "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "maneuver_completed": status == "met",
            "physical_checks": {"maneuver": {"status": status,
                                              "method": method, "sources": sources}},
            "realized_observables": observed,
            "physical_acceptance_claimed": False,
            "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=tuple(REQUESTS), required=True)
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if args.history.exists() or args.result.exists():
        raise ValueError("physical probe outputs must be fresh")
    if args.kind != "missing_evidence":
        args.history.parent.mkdir(parents=True, exist_ok=True)
        args.history.write_text("".join(json.dumps(row, allow_nan=False) + "\n"
                                        for row in history_for(scene_for(args.case), args.kind)))
    result = evaluate(args.case, args.kind, args.history)
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": result["case_id"], "kind": args.kind,
                      "status": result["physical_checks"]["maneuver"]["status"],
                      "diagnostic_fixture": True}))


if __name__ == "__main__":
    main()
