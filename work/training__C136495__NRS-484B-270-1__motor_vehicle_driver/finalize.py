"""Saved-only exact bicycle-rider analysis and canonical Native result writer."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from finalize_rider import finalize as rider_measurements


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def rows(root: Path, name: str) -> list[dict]:
    return [json.loads(line) for line in required(root, name).read_text().splitlines()]


def measure_interaction(root: str | Path) -> dict:
    root = Path(root)
    inputs = ("actor-frames.jsonl", "camera-frame-map.jsonl",
              "classification.json", "rider-binding.json")
    for name in inputs:
        required(root, name)
    value = rider_measurements(root)
    return {"value": value, "method": "measure_interaction",
            "sources": {name: digest(root / name) for name in inputs}}


def check_original_join(root: Path) -> list[dict]:
    actor = rows(root, "actor-frames.jsonl")
    camera = rows(root, "camera-frame-map.jsonl")
    trace = rows(root, "trace.jsonl")
    evidence = rows(root, "capture/evidence.jsonl")
    frame_map = rows(root, "video_frames.jsonl")
    if any(len(part) != 600 for part in (actor, camera, trace, evidence, frame_map)):
        raise ValueError("Missing 600-frame original source join")
    for index, (a, c, t, e, m) in enumerate(zip(actor, camera, trace, evidence, frame_map)):
        frame = m["native_frame"]
        if m["video_frame"] != index or any(x != frame for x in (
            m["carla_frame"], a["native_frame"], c["native_frame"],
            t["frame"], e["original_frame"]
        )):
            raise ValueError("Original actor, camera, trace and video frame join differs")
        if any(abs(x - m["time_s"]) > .051 for x in (
            a["time_s"], c["time_s"], t["time_s"], e["recording_time_s"]
        )):
            raise ValueError("Original actor, camera, trace and video time join differs")
    capture = json.loads(required(root, "capture/manifest.json").read_text())
    if capture.get("frames") != 600 or capture.get("extraction_confirmed") is not True:
        raise ValueError("Original Core extraction incomplete")
    return actor


def rebuild_channels(root: Path, actor_rows: list[dict], config: dict) -> None:
    folder = root / "channels"
    folder.mkdir(exist_ok=False)
    channels = config["mandatory_channels"]
    previous_speed = None
    previous_yaw = None
    widths = json.loads((root / "classification.json").read_text())["observed_body_width_m"]
    for name in channels:
        with (folder / (name + ".jsonl")).open("x") as stream:
            for row in actor_rows:
                ego, rider = row["actors"]["ego"], row["actors"]["rider"]
                if name == "ru.bicycle":
                    value = {"requested_class": "bicycle", "original_actor_id": rider.get("actor_id"),
                             "lawful_status": "unresolved"}
                elif name in ("ru.electric_bicycle", "ru.electric_scooter"):
                    value = {"requested_class": name.split(".", 1)[1],
                             "selected_in_this_fixture": False,
                             "alternative_original_review_pending": True}
                elif name == "kin.velocity":
                    value = {"rider_speed_mps": rider["speed_mps"],
                             "ego_speed_mps": ego.get("speed_mps")}
                elif name == "drv.time_to_conflict":
                    relative_speed = (ego.get("speed_mps") or 0) - rider["speed_mps"]
                    offset = rider["x_m"] - ego["x_m"]
                    value = {"engineering_time_to_longitudinal_overlap_s":
                             max(0, offset / relative_speed) if relative_speed > .05 and offset > 0 else None,
                             "legal_interference_threshold": None}
                elif name == "rel.surface_gap":
                    value = {"lateral_m": abs(rider["y_m"] - ego["y_m"]) -
                             (widths["ego"] + widths["rider"]) / 2,
                             "longitudinal_offset_m": rider["x_m"] - ego["x_m"]}
                elif name == "drv.hard_deceleration":
                    value = {"rider_deceleration_mps2":
                             None if previous_speed is None else
                             (previous_speed - rider["speed_mps"]) * 20,
                             "causal_interference": "unresolved"}
                elif name == "kin.yaw_rate":
                    yaw = rider["yaw_rad"]
                    value = {"rider_yaw_rate_rps": None if previous_yaw is None else
                             math.atan2(math.sin(yaw - previous_yaw),
                                        math.cos(yaw - previous_yaw)) * 20}
                else:
                    raise ValueError("Unimplemented mandatory observation: " + name)
                stream.write(json.dumps({"native_frame": row["native_frame"],
                                         "time_s": row["time_s"], "value": value},
                                        allow_nan=False) + "\n")
                previous_speed = rider["speed_mps"]
                previous_yaw = rider["yaw_rad"]
            previous_speed = None
            previous_yaw = None


def finalize(attempt: str | Path, output: str | Path) -> dict:
    from worker_exchange.native_output import physical_result, write_result

    root = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (root / "result.json").exists():
        raise ValueError("Use a fresh saved analysis workspace")
    config = json.loads(required(root, "config.json").read_text())
    interaction = measure_interaction(root)
    actor_rows = check_original_join(root)
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        required(root, name + ".mkv")
    rebuild_channels(root, actor_rows, config)
    observed = interaction["value"]
    intrusion = config["selected_case_id"].endswith("__probe_b")
    moved = observed["first_ego_lateral_change_frame"] is not None
    match = moved == intrusion
    videos = [name + ".mkv" for name in
              ("overview", "approach", "reference_corner", "driver_reference")]
    result = {"case_id": config["selected_case_id"],
              "measured_values": {"rider_interaction": observed},
              "target_checks": [{"target": "requested ego lateral route contrast",
                                 "requested": intrusion, "measured": moved,
                                 "method": "original frame-joined ego pose and rider body separation",
                                 "tolerance": "0.1 m engineering route observation, no legal cutoff",
                                 "matched": match, "physical_cause_confirmed": False,
                                 "cause_evidence": ["actor-frames.jsonl", "classification.json"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "saved source review pending",
              "physical_failure_flags": ["rider classification, lawful riding and camera visibility require independent original review"],
              "trace_reference": "trace.jsonl", "video_references": videos,
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": [
                  {"name": item["name"], "unit": item["unit"],
                   "reference": "channels/" + item["name"] + ".jsonl"}
                  for item in config["recording_description"]["channels"]],
              "realized_observables": {}, "accepted": False,
              "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    report = {"format": "c136495-saved-analysis-v1",
              "case_id": config["selected_case_id"],
              "measurements": {"rider_interaction": interaction},
              "physical_checks": result["physical_checks"],
              "realized_observables": result["realized_observables"],
              "original_native_observed": result["provenance_kind"] == "native",
              "rider_lawful_status": "unresolved", "driver_intent": "unresolved",
              "causal_interference": "unresolved", "legal_outcome_asserted": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
