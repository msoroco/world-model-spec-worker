"""Saved-only source joins for the two observed lane-change prerequisites.

An observed input event is not a finding about driver cognition or legal safety.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image

from camera_capture import SIZES
from finalize_lane_change import finalize
from native_construction import ASSIGNMENT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def rows(root, name, count):
    value = [json.loads(line) for line in required(root, name).read_text().splitlines()]
    if len(value) != count:
        raise ValueError("saved original source frame count differs: " + name)
    return value


def audit_camera_sources(root, capture, frame_map):
    source = required(root, "original-camera-frames/camera-manifest.json")
    if sha(source) != capture.get("camera_manifest", {}).get("sha256"):
        raise ValueError("original four-camera manifest SHA256 differs")
    cameras = json.loads(source.read_text())
    if not isinstance(cameras, list) or len(cameras) != 900:
        raise ValueError("original four-camera history incomplete")
    for index, (camera, clock) in enumerate(zip(cameras, frame_map)):
        if (camera.get("frame") != index or
                camera.get("native_frame") != clock.get("frame") or
                camera.get("native_elapsed_s") != clock.get("t_s") or
                set(camera.get("views", {})) != set(SIZES)):
            raise ValueError("original camera and Native frame/time join differs")
        for name, (width, height) in SIZES.items():
            entry = camera["views"][name]
            if entry.get("path") != f"{name}-{index:06d}.png":
                raise ValueError("original camera frame path differs")
            png = required(root, "original-camera-frames/" + entry["path"])
            if sha(png) != entry.get("sha256"):
                raise ValueError("original camera pixel SHA256 differs")
            with Image.open(png) as decoded:
                decoded.load()
                if decoded.format != "PNG" or decoded.size != (width, height):
                    raise ValueError("original camera pixel profile differs")
    return {"camera_manifest_sha256": sha(source), "joined_frames": 900,
            "decoded_original_png_frames": 3600,
            "physical_pixel_review": "unresolved"}


def build_report(attempt):
    root = Path(attempt).resolve()
    config = json.loads(required(root, "config.json").read_text())
    case = config.get("selected_case_id")
    if not isinstance(case, str) or not case.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact selected lane-change case differs")
    capture_path = required(root, "lane-change-capture-receipt.json")
    capture = json.loads(capture_path.read_text())
    if capture.get("native_frame_count") != 900:
        raise ValueError("complete Native acquisition absent")
    inventory_path = required(root, "readback-inventory.json")
    inventory = json.loads(inventory_path.read_text())
    if inventory != capture.get("readback_inventory"):
        raise ValueError("captured readback inventory differs")
    measured = finalize(root, inventory, case)
    frame_map = json.loads(required(root, "frame_map.json").read_text())["samples"]
    if len(frame_map) != 900:
        raise ValueError("900 original Native clock samples required")
    traffic = rows(root, "target-traffic-history.jsonl", 900)
    if sha(root / "target-traffic-history.jsonl") != capture.get("target_traffic", {}).get("sha256"):
        raise ValueError("original target-lane traffic SHA256 differs")
    for clock, target in zip(frame_map, traffic):
        if target.get("frame") != clock.get("frame") or target.get("t_s") != clock.get("t_s"):
            raise ValueError("target-lane traffic Native frame/time join differs")
    driver_rows = rows(root, "original-driver-input.jsonl", 900)
    if sha(root / "original-driver-input.jsonl") != capture.get("original_driver_input", {}).get("sha256"):
        raise ValueError("original independent driver-input SHA256 differs")
    source_id = capture["original_driver_input"].get("source_id")
    for clock, driver in zip(frame_map, driver_rows):
        if (driver.get("frame") != clock.get("frame") or driver.get("t_s") != clock.get("t_s") or
                driver.get("source_kind") != "original_driver_input" or
                driver.get("source_id") != source_id):
            raise ValueError("independent driver-input Native frame/time join differs")
    camera = audit_camera_sources(root, capture, frame_map)
    site = required(root, "reviewed-site.json")
    site_packet = json.loads(site.read_text())
    if not site_packet.get("reviewed_provenance"):
        raise ValueError("reviewed original site provenance absent")
    fixed = {"reviewed_site_sha256": sha(site),
             "source_lane_id": site_packet["lanes"]["source"]["lane_id"],
             "destination_lane_id": site_packet["lanes"]["destination"]["lane_id"],
             "ego_blueprint": site_packet["ego_blueprint"],
             "target_vehicle_blueprint": site_packet["target_vehicle_blueprint"],
             "target_traffic_plan_sha256": digest({"spawn": site_packet["target_spawn_xyz_yaw"],
                  "route": site_packet["lanes"]["destination"]["centerline_world_xyz_m"]}),
             "camera_plan_sha256": digest({"poses": site_packet["camera_poses_xyz_pitch_yaw"],
                                            "sizes": SIZES}),
             "capture_duration_s": config["duration_s"],
             "capture_rate_hz": config["rate_hz"]}
    sources = {name: sha(required(root, name)) for name in (
        "lane-change-capture-receipt.json", "readback-inventory.json",
        "frame_map.json", "ego_pose.json", "native_signal.json", "driver_check.json",
        "original-driver-input.jsonl", "target-traffic-history.jsonl",
        "original-camera-frames/camera-manifest.json", "reviewed-site.json")}
    return {"format": "c144550-saved-lane-change-report-v1", "case_id": case,
        "analysis_complete": True, "measurements": measured,
        "original_source_hashes": sources,
        "fixed_context": fixed,
        "camera_audit": camera,
        "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
        "limitations": ["An observed check is not proof of ascertainment or safety.",
                        "Original motion, traffic gap, and pixels require independent local review."]}


def write_selected_result(root, report):
    """Project immutable saved packets into the runtime recording contract."""
    if (root / "result.json").exists():
        raise ValueError("selected saved result already exists")
    config = json.loads(required(root, "config.json").read_text())
    description = config["recording_description"]
    packet_names = {"original_lane_and_pose": "ego_pose.json",
                    "native_signal_state": "native_signal.json",
                    "independent_driver_input": "driver_check.json"}
    streams = {name: json.loads(required(root, filename).read_text())["samples"]
               for name, filename in packet_names.items()}
    streams["target_lane_traffic"] = rows(root, "target-traffic-history.jsonl", 900)
    streams["four_camera_views"] = json.loads(required(root,
        "original-camera-frames/camera-manifest.json").read_text())
    for values in streams.values():
        if len(values) != 900:
            raise ValueError("selected recording channel missing original frames")
    channel_root = root / "channels"
    channel_root.mkdir(exist_ok=False)
    evidence = []
    for descriptor in description["channels"]:
        name = descriptor["name"]
        if name not in streams:
            raise ValueError("selected recording channel lacks source: " + name)
        target = channel_root / (name + ".jsonl")
        with target.open("x", encoding="utf-8") as output:
            for row in streams[name]:
                output.write(json.dumps({"time_s": row.get("t_s", row.get("native_elapsed_s")),
                                         "value": row}, separators=(",", ":"), allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": descriptor["unit"],
                         "reference": str(target.relative_to(root))})
    context = channel_root / "reviewed_marked_multilane_highway.json"
    context.write_text(json.dumps({"reviewed_marked_multilane_highway": json.loads(
        required(root, "reviewed-site.json").read_text())},
        separators=(",", ":"), allow_nan=False) + "\n")
    evidence.append({"name": "reviewed_marked_multilane_highway",
                     "unit": description["context_inputs"][0]["unit"],
                     "reference": str(context.relative_to(root))})
    clock = rows(root, "video_frames.jsonl", 900)
    original = rows(root, "trace.jsonl", 900)
    if any(a.get("frame") != b.get("carla_frame") or a.get("time_s") != b.get("time_s")
           for a, b in zip(original, clock)):
        raise ValueError("original trace/video Native frame/time join differs")
    measured = report["measurements"]
    departure = measured["departure_bracket_indices"][-1]
    site = json.loads(required(root, "reviewed-site.json").read_text())
    end = streams["original_lane_and_pose"][-1]
    destination = site["lanes"]["destination"]["centerline_world_xyz_m"]
    end_distance = min(math.hypot(end["x_m"] - point[0], end["y_m"] - point[1])
                       for point in destination)
    completed = end_distance <= 1.0 and departure < 899
    sources = report["original_source_hashes"]
    status = lambda achieved: "met" if achieved else "not_met"
    setup = {"status": "met", "method": "reviewed_original_marked_lane_packet",
             "intervals": [], "sources": {"reviewed-site.json": sources["reviewed-site.json"]}}
    target = {"status": status(departure < 899),
              "method": "original_source_lane_offset_departure",
              "intervals": [measured["departure_bracket_indices"]],
              "sources": {"ego_pose.json": sources["ego_pose.json"]}}
    maneuver = {"status": status(completed),
                "method": "original_end_pose_to_reviewed_destination_centerline_le_1m",
                "observed": {"final_destination_center_distance_m": end_distance},
                "intervals": [measured["departure_bracket_indices"], [899, 899]],
                "sources": {"ego_pose.json": sources["ego_pose.json"],
                            "reviewed-site.json": sources["reviewed-site.json"]}}
    for name in ("overview", "approach", "reference_corner", "driver_reference", "raw"):
        required(root, name + ".mkv")
    result = {"case_id": report["case_id"], "measured_values": measured,
              "target_checks": [{"target": "observed_original_lane_departure",
                  "requested": True, "measured": True, "method": target["method"],
                  "tolerance": 0.05, "matched": True,
                  "physical_cause_confirmed": False,
                  "cause_evidence": target["sources"]}],
              "setup_confirmed": True, "behavior_attempted": True,
              "maneuver_completed": completed,
              "termination_reason": "Saved original source analysis; legal safety unresolved",
              "physical_failure_flags": [],
              "physical_checks": {"setup": setup, "target": target, "maneuver": maneuver},
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {"final_destination_center_distance_m": {
                  "value": end_distance, "unit": "m",
                  "statistic": "minimum sampled centerline point distance",
                  "method": maneuver["method"], "time_window": "final original frame",
                  "reference": "channels/original_lane_and_pose.jsonl"}},
              "physical_acceptance_claimed": False,
              "legal_acceptance_claimed": False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    (root / "result.json").write_text(json.dumps(result, indent=2,
        sort_keys=True, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    if not output.is_relative_to(root):
        raise ValueError("saved analysis output must remain in saved attempt")
    report = build_report(root)
    write_selected_result(root, report)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
