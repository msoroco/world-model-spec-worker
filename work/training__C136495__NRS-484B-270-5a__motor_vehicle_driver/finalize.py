"""Saved-only cyclist due-care measurements and canonical Native result writer."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from finalize_due_care import finalize as due_care_measurements


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
              "response-control.jsonl", "classification.json",
              "collision-events.jsonl", "rider-binding.json")
    for name in inputs:
        required(root, name)
    value = due_care_measurements(root)
    return {"value": value, "method": "measure_interaction",
            "sources": {name: digest(root / name) for name in inputs}}


def measure_driver_role(root: str | Path) -> dict:
    root = Path(root)
    inputs = ("classification.json", "actor-frames.jsonl")
    for name in inputs:
        required(root, name)
    classification = json.loads((root / "classification.json").read_text())
    first = rows(root, "actor-frames.jsonl")[0]["actors"]["ego"]
    if classification.get("driver_actor_role") != "motor_vehicle_driver" or (
        classification.get("driver_blueprint_id") != first.get("blueprint_id")
    ):
        raise ValueError("Driver classification differs from original actor source")
    return {"value": {"driver_actor_role": classification["driver_actor_role"],
                       "driver_blueprint_id": first["blueprint_id"],
                       "actual_driver_identity": "unresolved"},
            "method": "measure_driver_role",
            "sources": {name: digest(root / name) for name in inputs}}


def measure_bicycle_scope(root: str | Path) -> dict:
    root = Path(root)
    inputs = ("classification.json", "actor-frames.jsonl")
    for name in inputs:
        required(root, name)
    classification = json.loads((root / "classification.json").read_text())
    if classification.get("requested_rider_vehicle_type") != "bicycle":
        raise ValueError("Requested selected bicycle branch differs")
    if classification.get("actual_person_riding") != "unresolved" or (
        classification.get("moped_exclusion") != "unresolved"
    ):
        raise ValueError("Unsupported selected bicycle qualification claim")
    return {"value": {"requested_branch": "person riding a bicycle",
                       "native_wheel_radii_m": classification["native_wheel_radii_m"],
                       "actual_person_and_qualifying_bicycle": "unresolved"},
            "method": "measure_bicycle_scope",
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
    contact_frames = {row["native_frame"] for row in rows(root, "collision-events.jsonl")}
    for name in channels:
        with (folder / (name + ".jsonl")).open("x") as stream:
            for row in actor_rows:
                ego, rider = row["actors"]["ego"], row["actors"]["rider"]
                if name == "ru.bicycle":
                    value = {"requested_class": "bicycle", "original_actor_id": rider.get("actor_id"),
                             "actual_person_riding": "unresolved", "moped_exclusion": "unresolved"}
                elif name in ("ru.electric_bicycle", "ru.electric_scooter"):
                    value = {"requested_class": name.split(".", 1)[1],
                             "selected_in_this_fixture": False,
                             "alternative_original_review_pending": True}
                elif name == "kin.speed":
                    value = {"rider_speed_mps": rider["speed_mps"],
                             "ego_speed_mps": ego["speed_mps"]}
                elif name == "drv.time_to_conflict":
                    relative_speed = ego["speed_mps"] - rider["speed_mps"]
                    offset = rider["x_m"] - ego["x_m"]
                    value = {"engineering_time_to_longitudinal_overlap_s":
                             max(0, offset / relative_speed) if relative_speed > .05 and offset > 0 else None,
                             "legal_due_care_threshold": None}
                elif name == "rel.surface_gap":
                    center = math.hypot(rider["x_m"] - ego["x_m"], rider["y_m"] - ego["y_m"])
                    er = math.hypot(ego["body_length_m"], ego["body_width_m"]) / 2
                    rr = math.hypot(rider["body_length_m"], rider["body_width_m"]) / 2
                    value = {"surface_gap_m": center - er - rr,
                             "longitudinal_offset_m": rider["x_m"] - ego["x_m"]}
                elif name == "rel.contact":
                    value = {"original_collision_sensor_event": row["native_frame"] in contact_frames,
                             "other_actor_classification": "unresolved"}
                elif name == "drv.hard_deceleration":
                    value = {"ego_acceleration_mps2":
                             None if previous_speed is None else
                             (ego["speed_mps"] - previous_speed) * 20,
                             "legal_late_reaction_threshold": None}
                else:
                    raise ValueError("Unimplemented mandatory observation: " + name)
                stream.write(json.dumps({"native_frame": row["native_frame"],
                                         "time_s": row["time_s"], "value": value},
                                        allow_nan=False) + "\n")
                previous_speed = ego["speed_mps"]
            previous_speed = None


def finalize(attempt: str | Path, output: str | Path) -> dict:
    from worker_exchange.native_output import physical_result, write_result

    root = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (root / "result.json").exists():
        raise ValueError("Use a fresh saved analysis workspace")
    config = json.loads(required(root, "config.json").read_text())
    interaction = measure_interaction(root)
    driver_role = measure_driver_role(root)
    bicycle_scope = measure_bicycle_scope(root)
    selection = json.loads(required(root, "candidate-selection.json").read_text())
    if interaction["value"]["case_id"] != config["selected_case_id"]:
        raise ValueError("Saved source differs from exact selected case")
    if interaction["value"]["candidate_id"] != selection.get("candidate_id"):
        provenance = json.loads(required(root, "acquisition-provenance.json").read_text())
        if provenance.get("diagnostic_fixture") is not True or (
            provenance.get("provenance_kind") != "synthetic_fixture"
        ):
            raise ValueError("Saved Native source differs from selected candidate")
    actor_rows = check_original_join(root)
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        required(root, name + ".mkv")
    rebuild_channels(root, actor_rows, config)
    observed = interaction["value"]
    condition = "early_response" if config["selected_case_id"].endswith("__condition_a") else "later_response"
    if observed["condition"] != condition:
        raise ValueError("Measured response case differs from requested condition")
    videos = [name + ".mkv" for name in
              ("overview", "approach", "reference_corner", "driver_reference")]
    result = {"case_id": config["selected_case_id"],
              "measured_values": {"cyclist_interaction": observed},
              "target_checks": [{"target": "requested longitudinal response contrast",
                                 "requested": condition,
                                 "measured": observed["minimum_longitudinal_acceleration_mps2"],
                                 "method": "original frame-joined ego pose, speed, gap and collision sensor",
                                 "tolerance": "engineering response observation; no legal due-care cutoff",
                                 "matched": False, "physical_cause_confirmed": False,
                                 "cause_evidence": ["actor-frames.jsonl", "collision-events.jsonl", "classification.json"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "saved source review pending",
              "physical_failure_flags": ["person riding, bicycle qualification, driver response and camera visibility require independent original review"],
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
    report = {"format": "c136495-due-care-saved-analysis-v1",
              "case_id": config["selected_case_id"],
              "measurements": {"cyclist_interaction": interaction,
                               "driver_role": driver_role,
                               "bicycle_scope": bicycle_scope},
              "physical_checks": result["physical_checks"],
              "realized_observables": result["realized_observables"],
              "original_native_observed": result["provenance_kind"] == "native",
              "person_riding_bicycle": "unresolved",
              "bicycle_qualification": "unresolved",
              "due_care_judgment": "unresolved", "legal_outcome_asserted": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
