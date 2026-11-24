"""Saved-only crossing stop measurements from one closed, source-bound attempt.

Engineering observations remain separate from whether NRS 484B.560(3) applies
or was satisfied. A fixture or requested control never establishes compliance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from native_camera import VIEWS
from native_scene import inspect
from owner_release import verify_release


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _document(path: Path) -> dict:
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _motion(row: dict, name: str) -> tuple[float, float, float, float, float, float, int]:
    subject = row.get(name)
    if not isinstance(subject, dict):
        raise ValueError("original " + name + " motion missing")
    position, velocity = subject.get("position_m"), subject.get("velocity_mps")
    extent, yaw, actor_id = (subject.get("bbox_half_extent_m"),
                             subject.get("heading_deg"), subject.get("actor_id"))
    if (not isinstance(position, list) or len(position) != 3 or
            not isinstance(velocity, list) or len(velocity) != 3 or
            not isinstance(extent, list) or len(extent) != 3 or
            type(yaw) not in (int, float) or not math.isfinite(yaw) or
            type(actor_id) is not int or actor_id < 0 or
            any(type(value) not in (int, float) or not math.isfinite(value)
                for value in position + velocity + extent) or
            any(value <= 0 for value in extent)):
        raise ValueError("original " + name + " motion invalid")
    return (float(position[0]), float(position[1]),
            math.dist(velocity, [0., 0., 0.]), float(extent[0]),
            float(extent[1]), float(yaw), actor_id)


def _heading_difference(yaw: float, direction: int) -> float:
    intended = 0. if direction == 1 else 180.
    return abs((yaw - intended + 180.) % 360. - 180.)


def _recording_plan(case_id: str) -> dict:
    proposals = _document(Path(__file__).resolve().parent / "proposals/cases.json")
    matches = [item["recording_description"] for item in proposals["cases"]
               if item["case_id"] == case_id]
    if len(matches) != 1:
        raise ValueError("exact recording plan missing")
    return matches[0]


def _recording_values(row: dict, packet: dict) -> dict:
    ego = row["ego"]
    direction = packet["approach_direction"]
    x, y, speed, length, width, _, _ = _motion(row, "ego")
    right_y = packet["slots"][packet["rightmost_feasible_slot"]]["y_m"]
    before_rail = direction * (packet["rail_line_x_m"] - x) > 0
    front_distance = direction * (packet["stop_line_x_m"] - x) - length
    views = {name: camera["sha256"] for name, camera in row["camera_sources"].items()}
    return {
        "crossing_stop_episode": {"speed_mps": speed, "before_rail": before_rail,
                                  "front_bumper_distance_m": front_distance,
                                  "stop_line_x_m": packet["stop_line_x_m"]},
        "subject_body_footprint": {"position_m": ego["position_m"],
                                   "heading_deg": ego["heading_deg"],
                                   "bbox_half_extent_m": ego["bbox_half_extent_m"]},
        "lateral_offset_from_feasible_right": direction * (y - right_y),
        "traffic_body_arrangement": {"ego": ego, "companion": row["companion"]},
        "marked_highway_lane_count": len(packet["marked_lanes"]),
        "crossing_sign_or_signal_views": views,
        "road_edge_and_subject_views": views,
        "queue_and_marking_views": views,
        "stopping_required": packet["stopping_required_context"],
        "highway_boundary": {"right_y_m": packet["highway_right_y_m"],
                             "left_y_m": packet["highway_left_y_m"]},
        "rightmost_feasible_position": packet["slots"][packet["rightmost_feasible_slot"]],
        "subject_lateral_position": y,
        "traffic_queue_arrangement": {"ego": ego, "companion": row["companion"]},
    }


def _recording_context(packet: dict, source_hash: str) -> dict:
    identity = {"source_packet_sha256": source_hash, "source_sha256": packet["sources"]}
    return {
        "crossing_authority": {**identity, "instruction": packet["stopping_required_context"],
                               "sign_landmark_id": packet["sign_landmark_id"],
                               "rail_crossing_map_ref": packet["rail_crossing_map_ref"],
                               "stop_line_x_m": packet["stop_line_x_m"]},
        "highway_boundary": {**identity, "right_y_m": packet["highway_right_y_m"],
                             "left_y_m": packet["highway_left_y_m"]},
        "rightmost_feasible_position": {**identity,
                                        "slot": packet["rightmost_feasible_slot"],
                                        "position": packet["slots"][packet["rightmost_feasible_slot"]]},
        "lane_marking_inventory": {**identity, "marked_lanes": packet["marked_lanes"]},
    }


def _write_recording_evidence(attempt: Path, result: dict) -> None:
    packet = _document(attempt / "site/packet.json")
    trace = _rows(attempt / "trace.jsonl")
    channels = result["recording_description"]["channels"]
    contexts = result["recording_description"]["context_inputs"]
    channel_names = {channel["name"] for channel in channels}
    context_values = _recording_context(packet, sha(attempt / "site/packet.json"))
    context_names = {context["name"] for context in contexts}
    if not channel_names <= set(_recording_values(trace[0], packet)) or not context_names <= set(context_values):
        raise ValueError("recording implementation differs from exact plan")
    evidence_dir = attempt / "recording_evidence"
    evidence_dir.mkdir(exist_ok=False)
    streams = {name: [] for name in channel_names}
    for row in trace:
        values = _recording_values(row, packet)
        for name in streams:
            streams[name].append(json.dumps({"time_s": row["time_s"], "frame": row["frame"],
                                             "value": values[name]}, allow_nan=False) + "\n")
    for name, rows in streams.items():
        (evidence_dir / (name + ".jsonl")).write_text("".join(rows), encoding="utf-8")
    for name in context_names:
        value = context_values[name]
        (evidence_dir / (name + ".json")).write_text(
            json.dumps({name: value}, allow_nan=False) + "\n", encoding="utf-8")


def analyze(attempt: Path) -> tuple[dict, dict]:
    attempt = Path(attempt).resolve()
    verify_release(attempt)
    status = _document(attempt / "native-run-status.json")
    case_id = status.get("case_id")
    if (status.get("errors") != [] or
            status.get("capture", {}).get("frames") != 900 or
            status.get("restoration", {}).get("restored") is not True or
            status.get("retained_site_packet") != "site/packet.json"):
        raise ValueError("closed original Native capture and restoration required")
    packet_path = attempt / "site/packet.json"
    if not packet_path.is_file():
        raise ValueError("Missing required source: site/packet.json")
    packet, case, _ = inspect(packet_path, Path(__file__).resolve().parent / "case-plan.json",
                              case_id)
    source_hash = sha(packet_path)
    if source_hash != status.get("site_packet_sha256"):
        raise ValueError("retained original site packet hash differs")
    trace = _rows(attempt / "trace.jsonl")
    mapping = _rows(attempt / "video_frames.jsonl")
    if len(trace) != 900 or len(mapping) != 900:
        raise ValueError("original 900-frame capture duration differs")
    receipt = _document(attempt / "media-receipt.json")
    if (receipt.get("format") != "c202480-original-four-camera-media-v1" or
            receipt.get("frames") != 900 or
            receipt.get("source_packet_sha256") != source_hash or
            receipt.get("trace_sha256") != sha(attempt / "trace.jsonl") or
            receipt.get("frame_map_sha256") != sha(attempt / "video_frames.jsonl")):
        raise ValueError("original media/source receipt differs")
    videos = receipt.get("video_sha256")
    if not isinstance(videos, dict) or set(videos) != {name for name, _, _ in VIEWS}:
        raise ValueError("original four-view media receipt incomplete")
    for name in videos:
        video = attempt / (name + ".mkv")
        if not video.is_file() or sha(video) != videos[name]:
            raise ValueError("original four-view video bytes differ")
    previous = None
    stop_run = 0
    first_stop = None
    max_speed = 0.
    first_ego_x = None
    max_approach_displacement = 0.
    control_requested = False
    previous_motion = None
    aligned_queue_frames = 0
    first_queue_alignment = None
    stopped_right_offsets = []
    actor_ids = None
    direction = packet["approach_direction"]
    right_y = packet["slots"][packet["rightmost_feasible_slot"]]["y_m"]
    highway_low, highway_high = sorted((packet["highway_right_y_m"],
                                        packet["highway_left_y_m"]))
    for index, (row, mapped) in enumerate(zip(trace, mapping)):
        frame, time_s = row.get("frame"), row.get("time_s")
        if (row.get("case_id") != case_id or type(frame) is not int or
                type(time_s) not in (int, float) or not math.isfinite(time_s) or
                row.get("source_frame") != frame or
                row.get("source_packet_sha256") != source_hash or
                row.get("physical_acceptance_claimed") is not False or
                (previous and (frame != previous[0] + 1 or
                               not .049 <= time_s - previous[1] <= .051))):
            raise ValueError("original Native trace identity or cadence differs")
        previous = frame, time_s
        cameras, hashes = row.get("camera_sources"), mapped.get("camera_source_sha256")
        if (not isinstance(cameras, dict) or set(cameras) != set(videos) or
                not isinstance(hashes, dict) or set(hashes) != set(videos) or
                mapped.get("video_frame") != index or
                mapped.get("carla_frame") != frame or
                mapped.get("native_frame") != frame or
                mapped.get("time_s") != time_s or
                any(cameras[name].get("sha256") != hashes[name] for name in videos)):
            raise ValueError("original four-camera frame map join differs")
        x, y, speed, length, width, yaw, ego_id = _motion(row, "ego")
        velocity = row["ego"]["velocity_mps"]
        if (row.get("position") != {"x": row["ego"]["position_m"][0],
                                    "y": row["ego"]["position_m"][1],
                                    "z": row["ego"]["position_m"][2]} or
                row.get("position_m") != row["ego"]["position_m"] or
                row.get("velocity_mps") != row["ego"]["velocity_mps"] or
                row.get("heading_deg") != row["ego"]["heading_deg"] or
                type(row.get("speed_mps")) not in (int, float) or
                not math.isclose(row["speed_mps"], speed, rel_tol=0, abs_tol=1e-8) or
                type(row.get("speed_mph")) not in (int, float) or
                not math.isclose(row["speed_mph"] * .44704, speed, rel_tol=0, abs_tol=1e-8)):
            raise ValueError("original canonical trace summary differs from ego motion")
        if previous_motion is not None:
            px, py, pvx, pvy = previous_motion
            dt = time_s - trace[index - 1]["time_s"]
            expected_dx = (pvx + velocity[0]) * dt / 2
            expected_dy = (pvy + velocity[1]) * dt / 2
            if (abs((x - px) - expected_dx) > .25 or
                    abs((y - py) - expected_dy) > .25):
                raise ValueError("original ego motion discontinuity")
        previous_motion = (x, y, velocity[0], velocity[1])
        if first_ego_x is None:
            first_ego_x = x
        max_approach_displacement = max(max_approach_displacement,
                                        direction * (x - first_ego_x))
        controls = row.get("controls")
        if not isinstance(controls, dict) or not isinstance(controls.get("ego"), dict):
            raise ValueError("original Native ego control missing")
        ego_control = controls["ego"]
        if row.get("control") != ego_control:
            raise ValueError("original canonical control differs from ego control")
        throttle = ego_control.get("throttle")
        brake = ego_control.get("brake")
        if (type(throttle) not in (int, float) or type(brake) not in (int, float) or
                not math.isfinite(throttle) or not math.isfinite(brake) or
                not 0 <= throttle <= 1 or not 0 <= brake <= 1):
            raise ValueError("original Native ego control invalid")
        control_requested |= throttle > 0 or brake > 0
        if _heading_difference(yaw, direction) > 20.:
            raise ValueError("original ego heading differs from reviewed approach")
        if not (highway_low < y - width and y + width < highway_high):
            raise ValueError("original ego footprint leaves reviewed highway")
        companion = None
        if case["traffic_arrangement"] == "two_queues":
            companion = _motion(row, "companion")
            cx, cy, cspeed, clength, cwidth, cyaw, companion_id = companion
            if (companion_id == ego_id or
                    _heading_difference(cyaw, direction) > 20. or
                    not (highway_low < cy - cwidth and cy + cwidth < highway_high)):
                raise ValueError("original companion identity, heading or footprint differs")
        elif row.get("companion") is not None:
            raise ValueError("one-queue case has unexpected companion")
        current_ids = (ego_id, companion[-1] if companion else None)
        if actor_ids is None:
            actor_ids = current_ids
        elif current_ids != actor_ids:
            raise ValueError("original actor identity changed across frames")
        max_speed = max(max_speed, speed)
        before_rail = packet["approach_direction"] * (packet["rail_line_x_m"] - x) > 0
        front_distance = direction * (packet["stop_line_x_m"] - x) - length
        at_stop_line = 0 <= front_distance <= 3.
        if speed <= .1 and before_rail and at_stop_line:
            stop_run += 1
            stopped_right_offsets.append(direction * (y - right_y))
            if stop_run == 20 and first_stop is None:
                first_stop = {"frame": frame,
                              "control_requested_before_stop": control_requested,
                              "approach_displacement_before_stop_m":
                                  direction * (x - first_ego_x),
                              "ego_x_m": x,
                              "ego_y_m": y,
                              "ego_right_edge_clearance_m": abs(y - packet["highway_right_y_m"]) - width,
                              "front_bumper_distance_before_stop_line_m": front_distance,
                              "distance_before_stop_line_m": packet["approach_direction"] *
                                                              (packet["stop_line_x_m"] - x)}
        else:
            stop_run = 0
        if companion is not None:
            separated = abs(y - cy) > width + cwidth + .1
            longitudinal_overlap = abs(x - cx) <= length + clength
            if (speed <= .1 and cspeed <= .1 and before_rail and
                    direction * (packet["rail_line_x_m"] - cx) > 0 and
                    separated and longitudinal_overlap):
                aligned_queue_frames += 1
                if first_queue_alignment is None:
                    first_queue_alignment = {"frame": frame,
                                             "lateral_center_separation_m": abs(y - cy),
                                             "longitudinal_center_separation_m": abs(x - cx)}
    observations = {"first_one_second_stop": first_stop,
                    "maximum_ego_speed_mps": max_speed,
                    "maximum_approach_displacement_m": max_approach_displacement,
                    "authored_marked_lane_count": len(packet["marked_lanes"]),
                    "original_actor_ids": list(actor_ids),
                    "first_two_queue_alignment": first_queue_alignment,
                    "two_queue_aligned_frame_count": aligned_queue_frames,
                    "minimum_stopped_lateral_offset_from_reviewed_rightmost_m":
                        min(stopped_right_offsets) if stopped_right_offsets else None,
                    "source_frame_count": 900}
    measured = first_stop is not None
    completed = (measured and first_stop["control_requested_before_stop"] and
                 first_stop["approach_displacement_before_stop_m"] >= 2. and
                 (case["traffic_arrangement"] != "two_queues" or
                  aligned_queue_frames >= 20))
    recording_plan = _recording_plan(case_id)
    recording_evidence = [
        {"name": item["name"], "unit": item["unit"],
         "reference": "recording_evidence/" + item["name"] +
                      (".jsonl" if item in recording_plan["channels"] else ".json")}
        for item in recording_plan["channels"] + recording_plan["context_inputs"]]
    result = {"case_id": case_id, "setup_confirmed": True,
              "behavior_attempted": control_requested,
              "maneuver_completed": completed,
              "measured_values": observations,
              "crossing_observables": observations,
              "realized_observables": {},
              "target_checks": [{"target": "original_capture_frames", "requested": 900,
                                 "measured": len(trace), "method": "source-bound original trace and frame-map count",
                                 "tolerance": 0, "matched": len(trace) == 900,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": "Original frame count alone does not establish physical crossing causation"}],
              "termination_reason": "planned_45_second_capture_completed",
              "physical_failure_flags": {"physical_acceptance_unverified": True},
              "recording_description": recording_plan,
              "recording_evidence": recording_evidence,
              "physical_checks": {"one_second_pre_rail_stationary_observation": {
                  "status": "met" if measured else "not_met",
                  "method": "at least 20 contiguous original 20 Hz frames at <=0.1 m/s with front bumper 0 to 3 m before authored stop line",
                  "sources": {"trace.jsonl": sha(attempt / "trace.jsonl"),
                              "site/packet.json": source_hash}}},
              "legal_judgment": "unresolved", "physical_acceptance_claimed": False,
              "trace_reference": "trace.jsonl",
              "video_frame_map_reference": "video_frames.jsonl",
              "video_references": [name + ".mkv" for name in videos]}
    measurement_sources = {"trace.jsonl": sha(attempt / "trace.jsonl"),
                           "site/packet.json": source_hash,
                           "video_frames.jsonl": sha(attempt / "video_frames.jsonl")}
    selected_measurements = {
        "crossing_stop_observation": {
            "stopping_required_context": packet["stopping_required_context"],
            "governing_sign_landmark_id": packet["sign_landmark_id"],
            "rail_crossing_map_ref": packet["rail_crossing_map_ref"],
            "first_one_second_stop": first_stop,
            "source_frame_count": 900},
        "right_side_observation": {
            "highway_right_y_m": packet["highway_right_y_m"],
            "highway_left_y_m": packet["highway_left_y_m"],
            "rightmost_feasible_slot": packet["rightmost_feasible_slot"],
            "minimum_stopped_lateral_offset_m": observations[
                "minimum_stopped_lateral_offset_from_reviewed_rightmost_m"]},
        "two_lane_arrangement_observation": {
            "planned_arrangement": case["traffic_arrangement"],
            "first_two_queue_alignment": first_queue_alignment,
            "two_queue_aligned_frame_count": aligned_queue_frames},
        "marked_lane_qualification_observation": {
            "total_marked_highway_lane_count": len(packet["marked_lanes"]),
            "marked_lane_source_names": sorted(packet["sources"]),
            "qualification_boundary_count": 4}}
    report = {"format": "c202480-saved-crossing-analysis-v1",
              "case_id": case_id,
              "measurements": {key: {"method": "analyze", "value": value,
                                     "sources": measurement_sources}
                               for key, value in selected_measurements.items()},
              "media_receipt_sha256": sha(attempt / "media-receipt.json"),
              "legal_judgment": "unresolved", "physical_acceptance_claimed": False}
    return report, result


def finalize_attempt(attempt: Path, output: Path) -> dict:
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output != attempt / "analysis-report.json":
        raise ValueError("saved analysis must stay beside original attempt")
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("retain previous saved analysis")
    report, result = analyze(attempt)
    _write_recording_evidence(attempt, result)
    (attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize_attempt(args.attempt, args.output), indent=2))
