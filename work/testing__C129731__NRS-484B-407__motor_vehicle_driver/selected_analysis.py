"""Finalize original C129731 sight packets without assigning a legal verdict.

The source-shaped CPU tests exercise this entrypoint with generated packets.
Only a separately reviewed original Native acquisition may support delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sight_measurement import ASSIGNMENT, measure

INPUTS = ("inventory.json", "frame_map.json", "ego_motion.json",
          "sight_rays.json", "road_geometry.json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _recording_evidence(attempt: Path, report: dict, core_supplied: bool) -> list[dict]:
    """Write derived channel views while retaining the sealed source packets."""
    frame_map = json.loads((attempt / "frame_map.json").read_text())["frames"]
    motion = json.loads((attempt / "ego_motion.json").read_text())["samples"]
    rays = json.loads((attempt / "sight_rays.json").read_text())["samples"]
    if len(frame_map) != len(motion) or len(frame_map) != 900:
        raise ValueError("Original recording frame stream incomplete")
    grouped = {}
    for ray in rays:
        grouped.setdefault(ray["frame"], []).append(ray)
    times = {row["frame"]: row["time_s"] for row in frame_map}
    road = json.loads((attempt / "road_geometry.json").read_text())
    approach_path = attempt / "approach_motion.json"
    approach = json.loads(approach_path.read_text()) if approach_path.is_file() else None
    approach_by_frame = {row["frame"]: row for row in approach.get("samples", [])} if approach else {}
    channels = {
        "ego_motion": [{"time_s": row["time_s"], "value": row}
                       for row in motion],
        "sight_rays": [{"time_s": times[number], "value": grouped[number]}
                       for number in sorted(grouped)],
        "road_geometry": [{"time_s": row["time_s"], "value": road}
                          for row in frame_map],
        "approaching_vehicle_routes": [
            {"time_s": row["time_s"],
             "value": approach_by_frame.get(row["frame"],
                                             {"source_status": "no_position_sample_at_frame" if approach else
                                              "baseline_reference_no_approach_probe"})}
            for row in frame_map],
        "frame_map": [{"time_s": row["time_s"], "value": row}
                      for row in frame_map],
        "frame_join": [{"time_s": row["time_s"], "value": row}
                       for row in frame_map],
        "original_camera_index": [
            {"time_s": row["time_s"],
             "value": {"video_frame": index, "native_frame": row["frame"],
                       "source_videos_verified": core_supplied}}
            for index, row in enumerate(frame_map)],
    }
    if not all(channels.values()):
        raise ValueError("Original recording channel missing")
    folder = attempt / "channels"
    folder.mkdir(exist_ok=True)
    evidence = []
    for name, rows in channels.items():
        destination = folder / (name + ".jsonl")
        if destination.exists():
            raise ValueError("Refusing to overwrite derived recording channel")
        destination.write_text("".join(json.dumps(row, separators=(",", ":"),
                                          allow_nan=False) + "\n" for row in rows))
        evidence.append({"name": name, "unit": "structured record",
                         "reference": str(destination.relative_to(attempt))})
    contexts = {
        "case_setup": {"selected_case_id": report["case_id"],
                       "source_inventory_sha256": _sha(attempt / "inventory.json")},
        "qualified_road_and_vehicle": {
            "source_status": "review_pending", "road_source": _sha(attempt / "road_geometry.json")},
        "actual_driver_view_context": {
            "source_status": "review_pending", "legal_visibility_judgment": "unresolved"},
    }
    for name, value in contexts.items():
        destination = folder / (name + ".json")
        if destination.exists():
            raise ValueError("Refusing to overwrite derived recording context")
        destination.write_text(json.dumps({name: value}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": "source record" if name == "case_setup" else
                         "structured record",
                         "reference": str(destination.relative_to(attempt))})
    return evidence


def _check_core_alignment(attempt: Path) -> bool:
    """Join any supplied Core timeline to every original sight frame and time."""
    mapping_path = attempt / "video_frames.jsonl"
    trace_path = attempt / "trace.jsonl"
    if not mapping_path.exists() and not trace_path.exists():
        return False
    if not mapping_path.is_file() or not trace_path.is_file():
        raise ValueError("Core trace and video frame map must be supplied together")
    sight = json.loads((attempt / "frame_map.json").read_text())["frames"]
    mapping = _jsonl(mapping_path)
    trace = _jsonl(trace_path)
    if not (len(sight) == len(mapping) == len(trace) == 900):
        raise ValueError("Core and sight frame counts differ")
    for index, (original, frame, motion) in enumerate(zip(sight, mapping, trace)):
        if (frame.get("video_frame") != index or
                frame.get("carla_frame") != original["frame"] or
                frame.get("time_s") != original["time_s"] or
                motion.get("frame") != original["frame"] or
                motion.get("time_s") != original["time_s"]):
            raise ValueError("Core and sight frame identity differs")
    return True


def measure_original_sight(attempt: Path, case_id: str) -> dict:
    """Measure observed reversal and two-direction rays from sealed packets."""
    attempt = Path(attempt).resolve()
    for name in INPUTS:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    inventory = json.loads((attempt / "inventory.json").read_text())
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("Wrong selected reversal identity")
    for atom in ("frame_map", "ego_motion", "sight_rays", "road_geometry"):
        entry = inventory.get("sources", {}).get(atom, {})
        if entry.get("path") != atom + ".json":
            raise ValueError("Original packet path differs: " + atom)
    measured = measure(attempt, inventory, case_id)
    sources = {name: _sha(attempt / name) for name in INPUTS}
    values = {
        "heading_change_deg": measured["measured_heading_change_deg"],
        "turn_frame_count": measured["turn_frames"],
        "location_kind": measured["location_kind"],
        "opposing_blocked_ray_count": measured["blocked_ray_counts"]["ahead_opposing"],
        "following_blocked_ray_count": measured["blocked_ray_counts"]["behind_same_direction"],
        "two_direction_ray_count": measured["rays_checked"],
    }
    scope = ("diagnostic software fixture only; no Native or legal acceptance"
             if inventory.get("diagnostic_fixture") is True else
             "source-bound original sight measurement; legal judgment unresolved")
    return {"format": "c129731-selected-analysis-v1", "case_id": case_id,
            "scope": scope,
            "analysis_complete": True, "legal_verdict_claimed": False,
            "limitations": ["A diagnostic fixture proves software wiring only",
                            "Original media and physical completion need independent review",
                            "Statutory driver visibility remains unresolved"],
            "measurements": {key: {"value": value,
                                   "method": "measure_original_sight",
                                   "sources": sources}
                             for key, value in values.items()},
            "original_sight": measured}


def build_canonical_result(attempt: Path, report: dict) -> dict:
    """Build the Native result shape; physical completion uses saved evidence."""
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    if (config.get("selected_case_id") != report["case_id"] or
            config.get("law_id") != "NRS-484B-407" or
            config.get("cell_id") != "C129731" or
            config.get("actor") != "motor_vehicle_driver"):
        raise ValueError("Exact canonical reversal configuration changed")
    core_supplied = _check_core_alignment(attempt)
    if core_supplied:
        from native_camera_audit import audit as audit_native_cameras
        camera_audit = audit_native_cameras(attempt)
        if camera_audit.get("case_id") != report["case_id"]:
            raise ValueError("Original camera case differs from selected sight case")
        report["original_camera_audit"] = camera_audit
    values = report["measurements"]
    heading = values["heading_change_deg"]["value"]
    sources = values["heading_change_deg"]["sources"]
    checks = [{"target": "observed opposite-direction turn",
               "requested": True, "measured": heading >= 150,
               "method": "original frame-joined subject heading change",
               "tolerance": "150 degrees engineering observation minimum",
               "matched": heading >= 150, "physical_cause_confirmed": False,
               "cause_evidence": sources}]
    suffix = config["selected_case_id"].removeprefix(ASSIGNMENT + "__")
    if suffix != "distance_reference":
        probe = attempt / "approach_motion.json"
        if not probe.is_file():
            raise ValueError("Missing required source: approach_motion.json")
        inventory = json.loads((attempt / "inventory.json").read_text())
        reference = inventory.get("approach_probe", {})
        if (reference.get("path") != probe.name or
                reference.get("sha256") != _sha(probe)):
            raise ValueError("Original approach probe hash differs")
        packet = json.loads(probe.read_text())
        if packet.get("case_id") != report["case_id"] or packet.get("source_kind") != "original_native":
            raise ValueError("Original approach probe identity changed")
        target_ft = config["target_first_turn_distance_ft"]
        measured_m = packet.get("first_turn_distance_m")
        if (packet.get("probe_target_ft") != target_ft or
                type(measured_m) not in (int, float)):
            raise ValueError("Original approach probe target changed")
        target_m = target_ft * .3048
        matched = abs(measured_m - target_m) <= .1
        checks.append({"target": "first reversal approach distance",
                       "requested": target_m, "measured": measured_m,
                       "method": "original frame-joined vehicle positions",
                       "tolerance": .1, "matched": matched,
                       "physical_cause_confirmed": False,
                       "cause_evidence": {"approach_motion.json": _sha(probe)}})
    description = construction["recording_description"]
    declared = {channel.get("name") for channel in description.get("channels", [])}
    required = {"ego_motion", "sight_rays", "road_geometry", "approaching_vehicle_routes",
                "frame_map", "frame_join", "original_camera_index"}
    if not required <= declared or len(declared) != len(description["channels"]):
        raise ValueError("Required Native recording channels missing")
    evidence = _recording_evidence(attempt, report, core_supplied)
    result = {"case_id": report["case_id"],
              "measured_values": {key: item["value"] for key, item in values.items()},
              "target_checks": checks, "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved original evidence assessment pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description,
              "recording_evidence": evidence, "realized_observables": {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing to overwrite analysis output")
    case = args.case
    if case is None:
        case = json.loads((args.attempt / "config.json").read_text())["selected_case_id"]
    report = measure_original_sight(args.attempt, case)
    if args.finalize or (args.attempt / "construction.json").is_file():
        result_path = args.attempt / "result.json"
        if result_path.exists():
            raise ValueError("Refusing to overwrite canonical result")
        result = build_canonical_result(args.attempt, report)
        result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        report["physical_checks"] = result["physical_checks"]
        report["realized_observables"] = result["realized_observables"]
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
