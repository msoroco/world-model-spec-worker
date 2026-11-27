"""Freeze six exact stop constructions and source-bound diagnostic recipes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from author_semantics import RECORDING
from stop_model import ASSIGNMENT, CASES, LAW


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
FILES = ("runner.py", "native_stop.py", "stop_model.py", "analysis.py",
         "tests/test_stop_model.py")
CAMERAS = [{"name": name, "width": width, "height": height,
            "pose_strategy": strategy, "fov_deg": 90}
           for name, width, height, strategy in (
               ("overview", 1920, 1080, "reviewed full one-way roadway and traffic"),
               ("approach", 1280, 720, "reviewed ego approach, stop and follower"),
               ("reference_corner", 1280, 720, "reviewed roadway edge and passing space"),
               ("driver_reference", 1280, 720, "follower-mounted original reference"))]
MEASUREMENT_KEYS = ("complete_stop", "roadway_position", "traffic_effect",
                    "safety_context", "law_direction")
SOURCE_INPUTS = ("stop-history.jsonl", "stop-scene.json", "video_frames.jsonl", "trace.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def config_for(case):
    case_id = ASSIGNMENT + "__" + case.name
    return {"assignment_id": ASSIGNMENT, "selected_case_id": case_id,
            "supported_case_ids": [ASSIGNMENT + "__" + item.name for item in CASES],
            "law_id": LAW, "cell_id": "C150640", "actor": "motor_vehicle_driver",
            "rate_hz": 20, "duration_s": 45, "required_atoms": [], "source_packets": [],
            "cameras": CAMERAS,
            "engineering": {"stop_trigger_frame": 200},
            "physical_completion": {"criterion": "travel_progress",
                                    "motion_source": "trace.jsonl",
                                    "position_key": "position_m",
                                    "minimum_progress_m": 4,
                                    "minimum_samples": 2,
                                    "engineering_tolerances_not_legal": True},
            "case": {"case_id": case_id, "stop_surface": case.stop_surface,
                     "stop_reason": case.stop_reason,
                     "follower_action": case.follower_action,
                     "complete_stop_requested": case.complete_stop_requested,
                     "recording_description": RECORDING}}


def construction_for(case, config):
    files = [{"path": name, "source": str((ROOT / name).relative_to(REPO)),
              "content": (ROOT / name).read_text(encoding="utf-8")}
             for name in FILES]
    files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
    return {"law_id": LAW, "cell_id": "C150640", "actor": "motor_vehicle_driver",
            "case_id": config["selected_case_id"], "entrypoint": "runner.py",
            "files": files,
            "measurement_plan": [{"name": name, "method": "analysis.analyze",
                                  "sources": list(SOURCE_INPUTS)} for name in MEASUREMENT_KEYS],
            "recording_description": RECORDING,
            "static_checks": ["exact law/cell/actor/case and source packet identities",
                              "original one-way route, roadway/shoulder polygons and four footprint corners",
                              "two distinct vehicle identities and original frame/time join"],
            "termination_rules": ["45 seconds at 20 Hz through approach, stop or slow roll, and follower response"],
            "mechanisms": ["reviewed one-way Native map", "separate ego and follower controls",
                           "source-reviewed safety conflict or official-direction actor where selected",
                           "original vehicle body footprint and traffic-motion readback",
                           "four synchronized camera encoders and saved-only finalizer"]}


def diagnostic_for(case, template):
    spec = json.loads(json.dumps(template))
    trace = [json.loads(line) for line in spec["files"]["trace.jsonl"].splitlines() if line]
    mapping = [json.loads(line) for line in spec["files"]["video_frames.jsonl"].splitlines() if line]
    if len(trace) != len(mapping) or len(trace) < 8:
        raise ValueError("generic native-shaped fixture lacks enough frames")
    scene = {"format": "c150640-roadway-stop-diagnostic-v1",
             "source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
             "case_id": ASSIGNMENT + "__" + case.name,
             "one_way_route": [[0, 2], [100, 2]],
             "roadway_polygon": [[0, 0], [100, 0], [100, 4], [0, 4]],
             "shoulder_polygon": [[0, 5], [100, 5], [100, 8], [0, 8]],
             "passing_space_m": 3.5,
             "sources": {name: {"sha256": hashlib.sha256((name + case.name).encode()).hexdigest()}
                         for name in ("stop_purpose", "jurisdiction", "ego_driver",
                                      "roadway_boundary", "shoulder_boundary",
                                      "one_way_direction", "follower_driver")}}
    spec["files"]["stop-scene.json"] = json.dumps(scene) + "\n"
    spec["files"]["diagnostic-source-note.json"] = json.dumps({
        "source_kind": "synthetic_diagnostic_fixture", "accepted_original_source": False,
        "purpose": "CPU source-shape and finalizer test only; no physical or legal finding"}) + "\n"
    history = []
    for i, (telemetry, camera) in enumerate(zip(trace, mapping)):
        if (telemetry["frame"], telemetry["time_s"]) != (camera["carla_frame"], camera["time_s"]):
            raise ValueError("generic fixture frame/time mismatch")
        stopped = i >= 4 and case.complete_stop_requested
        y = 6.0 if case.stop_surface == "shoulder" else 1.0
        history.append({"original_frame": telemetry["frame"], "time_s": telemetry["time_s"],
                        "ego_id": 101, "follower_id": 102,
                        "ego_speed_mps": 0.0 if stopped else (1.2 if i >= 4 else 6.0),
                        "follower_speed_mps": (0.0 if i >= 6 else 5.0)
                            if case.follower_action == "follow_and_halt" else 6.0,
                        "ego_footprint_xy": [[10, y], [12, y], [12, y + 1], [10, y + 1]],
                        "follower_route_station_m": float(i * (2 if case.follower_action == "pass" else 1)),
                        "body_gap_m": 15.0 - i,
                        "follower_ahead_of_ego": case.follower_action == "pass" and i >= 7,
                        "conflict_readback": {"actor_id": 103, "position_xy": [14, 2]}
                            if case.stop_reason == "safety_conflict" else None,
                        "official_direction_readback": {"actor_id": 104, "state": "stop"}
                            if case.stop_reason == "official_direction" else None})
    spec["files"]["stop-history.jsonl"] = "".join(json.dumps(row) + "\n" for row in history)
    return spec


def main():
    template = json.loads((REPO / "runtime/fixtures/example.json").read_text(encoding="utf-8"))
    dispositions = json.loads((ROOT / "case-plan.json").read_text())["requirement_dispositions"]
    for index, case in enumerate(CASES):
        config = config_for(case)
        construction = construction_for(case, config)
        folder = ROOT if index == 0 else ROOT / "cases" / case.name
        write(folder / "config.json", config)
        write(folder / "construction.json", construction)
        fallback_config = json.loads(json.dumps(config))
        fallback_config["engineering"]["stop_trigger_frame"] = 170
        fallback = construction_for(case, fallback_config)
        write(ROOT / "cases" / case.name / "fallback1" / "construction.json", fallback)
        contract = {"format": "worker-measurement-contract",
                    "requirements": [{"disposition_index": i,
                                      "requirement": disposition["requirement"],
                                      "source": disposition["source"],
                                      "output_key": MEASUREMENT_KEYS[i],
                                      "method": "analyze", "value_type": "object",
                                      "kind": "measured" if i < 3 else "sourced_context",
                                      "inputs": list(SOURCE_INPUTS)}
                                     for i, disposition in enumerate(dispositions)],
                    "negative": {"remove": ["stop-scene.json"],
                                 "error_contains": "Missing required source: stop-scene.json"}}
        write(folder / "measurement-contract.json", contract)
        diagnostic = ROOT / ("diagnostic-" + case.name + ".json")
        diagnostic.write_text(json.dumps(diagnostic_for(case, template),
                                         separators=(",", ":"), ensure_ascii=False) + "\n",
                              encoding="utf-8")
        reference = {"source": str(diagnostic.relative_to(REPO)), "sha256": sha(diagnostic)}
        write(ROOT / ("diagnostic-" + case.name + "-recipe.json"),
              {"format": "worker-fixture-recipe",
               "sources": [{"path": "diagnostic-input.json", **reference}],
               "generator": reference})


if __name__ == "__main__":
    main()
