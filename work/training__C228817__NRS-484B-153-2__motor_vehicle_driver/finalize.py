"""Saved-only door measurement from original capture and separately reviewed pixels.

Actuator requests are never used as observations. The review file must be
authored after inspecting the four original camera streams.
"""

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from measure_door import FRAME_COUNT, VIEWS, measure
from native.door_interference import measure_trace


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def video_info(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=nb_read_frames,width,height", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=120)
    try:
        stream = json.loads(result.stdout)["streams"][0]
    except (ValueError, KeyError, IndexError):
        stream = {}
    if result.returncode or not all(type(stream.get(k)) is int and stream[k] > 0
                                   for k in ("width", "height")) or \
            not str(stream.get("nb_read_frames", "")).isdigit():
        raise ValueError("Original camera decode failed: " + path.name)
    return (int(stream["nb_read_frames"]), stream["width"], stream["height"])


def _review_sources(review, camera_hashes, camera_info, frame_count):
    if review.get("format") != "c228817-door-pixel-review-v1":
        raise ValueError("Independent original pixel review required")
    if review.get("camera_sha256") != camera_hashes:
        raise ValueError("Pixel review binds different camera bytes")
    if review.get("observed_traffic_side") not in ("left", "right") or \
            review.get("observed_door_side") != review["observed_traffic_side"]:
        raise ValueError("Reviewed traffic-side door orientation required")
    if not review.get("ground_plane_calibration_source"):
        raise ValueError("Original ground-plane calibration source required")
    observations = review.get("door_observations")
    if not isinstance(observations, list) or len(observations) != frame_count:
        raise ValueError("Every original frame needs reviewed door state")
    for i, row in enumerate(observations):
        if row.get("video_frame") != i or type(row.get("door_open")) is not bool:
            raise ValueError("Incomplete reviewed door frame")
        if row.get("source_camera") not in VIEWS or not row.get("pixel_box_xyxy"):
            raise ValueError("Door state needs reviewed source pixels")
        if not all(isinstance(row.get(key), list) and len(row[key]) == 2
                   for key in ("hinge_world_xy_m", "tip_world_xy_m")):
            raise ValueError("Original calibrated door hinge and tip required")
        x0, y0, x1, y1 = row["pixel_box_xyxy"]
        _, width, height = camera_info[row["source_camera"]]
        if not all(type(v) is int and v >= 0 for v in (x0, y0, x1, y1)) or \
                x1 <= x0 or y1 <= y0 or x1 > width or y1 > height:
            raise ValueError("Invalid reviewed door pixel box")
    events = review.get("transfer_events")
    if not isinstance(events, list) or not events:
        raise ValueError("Independent passenger or cargo transfer review required")
    for event in events:
        if event.get("kind") not in ("passenger", "cargo") or \
                event.get("source_camera") not in VIEWS or \
                not isinstance(event.get("pixel_box_xyxy"), list):
            raise ValueError("Transfer event needs reviewed source pixels")
        if event["kind"] == "passenger" and event.get("occupancy_delta_observed") not in (-1, 1):
            raise ValueError("Passenger occupancy change needs independent review")
        if event["kind"] == "cargo" and not event.get("cargo_actor_id_observed"):
            raise ValueError("Cargo identity needs independent review")
        x0, y0, x1, y1 = event["pixel_box_xyxy"]
        _, width, height = camera_info[event["source_camera"]]
        if not all(type(v) is int and v >= 0 for v in (x0, y0, x1, y1)) or \
                x1 <= x0 or y1 <= y0 or x1 > width or y1 > height:
            raise ValueError("Invalid reviewed transfer pixel box")
    return observations, events


def measure_open_duration(root, report):
    sources = ("native-door-trace.jsonl", "video_frames.jsonl",
               "door-pixel-review.json", "original-scene-review.json")
    return {"value": {name: report[name] for name in (
        "open_duration_s", "post_transfer_open_s", "open_frame", "close_frame",
        "passing_side", "door_side", "transfer_kinds")},
        "method": "measure_open_duration",
        "sources": {name: digest(required(root, name)) for name in sources}}


def measure_traffic_side(root, report):
    sources = ("door-pixel-review.json", "original-road.json",
               "native-door-trace.jsonl")
    return {"value": {"observed_door_side": report["door_side"],
                      "observed_passing_side": report["passing_side"],
                      "traffic_side_door": report["door_side"] == report["passing_side"]},
            "method": "measure_traffic_side",
            "sources": {name: digest(required(root, name)) for name in sources}}


def measure_transfer(root, report):
    sources = ("door-pixel-review.json", "original-transfer.json",
               "native-door-trace.jsonl")
    return {"value": {"reviewed_transfer_kinds": report["transfer_kinds"],
                      "transfer_frame": 200},
            "method": "measure_transfer",
            "sources": {name: digest(required(root, name)) for name in sources}}


def measure_interference_context(root, report):
    sources = ("door-pixel-review.json", "original-scene-review.json",
               "native-door-trace.jsonl", "video_frames.jsonl")
    return {"value": {"passing_response_after_door_motion": report["interference_diagnostics"]["passing_response_after_door_motion"],
                      "loading_activity_source": "door-pixel-review.json#transfer_events",
                      "interference_requires_contextual_review": True},
            "method": "measure_interference_context",
            "sources": {name: digest(required(root, name)) for name in sources}}


def interference_rows(trace, states, review, config, measured):
    """Source-bound geometry and response diagnostics, never a legal verdict.

    Each door pose is separately reviewed against an original camera with a
    ground-plane calibration. Native door requests do not supply pose.
    """
    if review.get("ground_plane_calibration_source") is None:
        raise ValueError("Original ground-plane calibration source required")
    rows, diagnostic_rows = [], []
    prior_speed = None
    transfer_frame = 200
    for i, (actor, observed) in enumerate(zip(trace, states)):
        hinge = observed.get("hinge_world_xy_m")
        tip = observed.get("tip_world_xy_m")
        position = actor.get("passing_position_m")
        velocity = actor.get("passing_velocity_mps")
        radius = actor.get("passing_radius_m")
        if not all(isinstance(v, list) and len(v) >= 2 for v in (hinge, tip, position, velocity)) or \
                type(radius) not in (int, float):
            raise ValueError("Original door pose and passing vehicle geometry required")
        numbers = [*hinge[:2], *tip[:2], *position[:2], *velocity[:2], radius]
        if not all(type(v) in (int, float) and math.isfinite(v) for v in numbers) or radius <= 0:
            raise ValueError("Invalid door or passing vehicle geometry")
        length = math.hypot(tip[0]-hinge[0], tip[1]-hinge[1])
        if length <= 0:
            raise ValueError("Degenerate reviewed door segment")
        angle = math.atan2(tip[1]-hinge[1], tip[0]-hinge[0])
        speed = math.hypot(velocity[0], velocity[1])
        if abs(speed - actor.get("passing_speed_mps", -1)) > 1e-3:
            raise ValueError("Passing speed and velocity source differ")
        ux, uy = tip[0]-hinge[0], tip[1]-hinge[1]
        projection = max(0.0, min(1.0, ((position[0]-hinge[0])*ux+(position[1]-hinge[1])*uy)/(length*length)))
        gap = math.hypot(position[0]-hinge[0]-projection*ux, position[1]-hinge[1]-projection*uy)-radius
        longitudinal = hinge[0]-position[0]
        ttc = longitudinal/velocity[0] if velocity[0] > 0 and longitudinal >= 0 else None
        decel = max(0.0, (prior_speed-speed)*20) if prior_speed is not None else 0.0
        prior_speed = speed
        rows.append({"frame": i, "time_s": i/20, "door_hinge_x_m": hinge[0], "door_hinge_y_m": hinge[1],
            "door_length_m": length, "door_angle_rad": angle,
            "passing_x_m": position[0], "passing_y_m": position[1], "passing_radius_m": radius,
            "passing_vx_mps": velocity[0], "passing_vy_mps": velocity[1],
            "vehicle_stopped": abs(actor["ego_speed_mps"]) <= 0.15,
            "door_open": observed["door_open"],
            "person_boarding_or_alighting": i == transfer_frame,
            "passing_vehicle_in_lane": (actor["passing_lateral_offset_m"] > 0.25)})
        diagnostic_rows.append({"door_to_vehicle_gap_m": gap if observed["door_open"] else None,
            "time_to_door_plane_s": ttc, "passing_deceleration_mps2": decel})
    scene = {"parked_vehicle_source": "native-door-trace.jsonl",
        "traffic_side_source": "door-pixel-review.json",
        "passing_lane_source": "original-road.json",
        "door_hinge_source": "door-pixel-review.json",
        "boarding_person_source": "door-pixel-review.json",
        "door_side": "closest_to_passing_traffic"}
    summary = measure_trace(rows, scene)
    summary["first_door_open_frame"] = measured["open_frame"]
    summary["transfer_frame"] = transfer_frame
    summary["passing_response_after_door_motion"] = [row["passing_deceleration_mps2"]
        for i, row in enumerate(diagnostic_rows) if i > measured["open_frame"]]
    summary["passing_response_after_door_motion"] = max(summary["passing_response_after_door_motion"], default=0.0)
    summary["legal_interference_conclusion"] = None
    return diagnostic_rows, summary


def derived_channels(root, config, frame_rows, trace, packet, measured):
    """Write derived channel streams after all original joins have passed."""
    names = [item["name"] for item in config["recording_description"]["channels"]]
    expected = ["sig.door_open", "kin.time", "drv.standing_or_parked",
                "ru.occupant_count", "ru.pedestrian", "st.lane",
                "rel.surface_gap", "drv.time_to_conflict", "drv.hard_deceleration", "kin.velocity"]
    if names != expected:
        raise ValueError("Frozen door recording description differs")
    channel_dir = root / "channels"
    channel_dir.mkdir(exist_ok=True)
    transfer_by_frame = {event["video_frame"]: event for event in packet["transfer_events"]}
    values = {
        "sig.door_open": lambda i: frame_rows[i]["door_open"],
        "kin.time": lambda i: frame_rows[i]["native_time_s"],
        "drv.standing_or_parked": lambda i: abs(trace[i]["ego_speed_mps"]) <= 0.15,
        "ru.occupant_count": lambda i: {"observed_delta":
            transfer_by_frame[i].get("occupancy_delta") if i in transfer_by_frame else None,
            "source_ref": "door-pixel-review.json#transfer_events" if i in transfer_by_frame else None},
        "ru.pedestrian": lambda i: {"actor_id": trace[i].get("pedestrian_actor_id"),
            "position_m": trace[i].get("pedestrian_position_m")},
        "st.lane": lambda i: {"passing_side": measured["passing_side"],
            "door_side": measured["door_side"],
            "lateral_offset_m": trace[i]["passing_lateral_offset_m"]},
        "rel.surface_gap": lambda i: {"value_m": measured["traffic_rows"][i]["door_to_vehicle_gap_m"],
            "source_ref": "door-pixel-review.json#door_observations/" + str(i)},
        "drv.time_to_conflict": lambda i: {"value_s": measured["traffic_rows"][i]["time_to_door_plane_s"],
            "source_ref": "native-door-trace.jsonl#" + str(i)},
        "drv.hard_deceleration": lambda i: {"value_mps2": measured["traffic_rows"][i]["passing_deceleration_mps2"],
            "source_ref": "native-door-trace.jsonl#" + str(i)},
        "kin.velocity": lambda i: {"passing_speed_mps": trace[i]["passing_speed_mps"],
            "source_ref": "native-door-trace.jsonl#" + str(i)},
    }
    for name in names:
        (channel_dir / (name + ".jsonl")).write_text("".join(json.dumps({
            "time_s": frame_rows[i]["native_time_s"], "value": values[name](i)},
            allow_nan=False) + "\n" for i in range(FRAME_COUNT)))
    return [{"name": name, "unit": "structured",
             "reference": "channels/" + name + ".jsonl"} for name in names]


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Use a fresh saved attempt; original sources are immutable")
    config = json.loads(required(attempt, "config.json").read_text())
    if config.get("duration_frames") != FRAME_COUNT or config.get("rate_hz") != 20:
        raise ValueError("Exact door capture window differs")
    mapping = rows(required(attempt, "video_frames.jsonl"))
    trace = rows(required(attempt, "native-door-trace.jsonl"))
    if len(mapping) != FRAME_COUNT or len(trace) != FRAME_COUNT:
        raise ValueError("Complete original frame and actor histories required")
    cameras = {name: required(attempt, name + ".mkv") for name in VIEWS}
    camera_hashes = {name: digest(path) for name, path in cameras.items()}
    camera_info = {name: video_info(path) for name, path in cameras.items()}
    if any(info[0] != FRAME_COUNT for info in camera_info.values()):
        raise ValueError("Four complete source camera streams required")
    review = json.loads(required(attempt, "door-pixel-review.json").read_text())
    if review.get("case_id") != config.get("case_id"):
        raise ValueError("Pixel review binds another exact case")
    states, events = _review_sources(review, camera_hashes, camera_info, FRAME_COUNT)
    scene = json.loads(required(attempt, "original-scene-review.json").read_text())
    if scene.get("case_id") != config.get("case_id") or \
            scene.get("source_kind") != "source_bound_native_setup":
        raise ValueError("Original scene review binds another case")
    sources = scene.get("sources", {})
    for name in ("map", "road", "transfer"):
        original = required(attempt, "original-" + name + ".json")
        if sources.get(name, {}).get("sha256") != digest(original):
            raise ValueError("Original scene source hash differs: " + name)
    transfer_setup = json.loads(required(attempt, "original-transfer.json").read_text())
    if transfer_setup.get("kind") != config.get("transfer_kind", "passenger"):
        raise ValueError("Original transfer setup differs from selected alternative")
    driver = trace[0].get("driver_actor_id")
    passing = trace[0].get("passing_actor_id")
    if not driver or not passing or driver == passing:
        raise ValueError("Distinct original driver and passing vehicle required")
    first_tick = mapping[0].get("native_frame")
    first_time = mapping[0].get("native_elapsed_s")
    if type(first_tick) is not int or type(first_time) not in (int, float):
        raise ValueError("Original Native frame/time origin required")
    frame_rows = []
    offsets = []
    for i, (frame, actor, observed) in enumerate(zip(mapping, trace, states)):
        if frame.get("video_frame") != i or actor.get("video_frame") != i or \
                frame.get("native_frame") != actor.get("native_frame") or \
                frame.get("native_frame") != first_tick + i or \
                abs(frame.get("native_elapsed_s", -1) - actor.get("native_elapsed_s", -2)) > 1e-5 or \
                abs(frame.get("native_elapsed_s", -1) - first_time - i / 20) > 1e-4:
            raise ValueError("Original frame/time join differs")
        if actor.get("driver_actor_id") != driver or actor.get("passing_actor_id") != passing:
            raise ValueError("Original actor identity changed")
        if actor.get("door_state_observed") is not None or actor.get("occupancy_delta_observed") is not None:
            raise ValueError("Command trace must not claim observed door or occupancy")
        offsets.append(actor.get("passing_lateral_offset_m"))
        frame_rows.append({"native_frame": frame["native_frame"],
            "video_frame": i, "native_time_s": frame["native_elapsed_s"],
            "door_open": observed["door_open"],
            "door_state_source_ref": "door-pixel-review.json#door_observations/" + str(i),
            "ego_speed_mps": actor["ego_speed_mps"],
            "ego_motion_source_ref": "native-door-trace.jsonl#" + str(i)})
    packet = {"source_kind": "native_trace",
        "source_sha256": digest(required(attempt, "native-door-trace.jsonl")),
        "frames": frame_rows,
        "cameras": {name: {"frame_count": FRAME_COUNT, "sha256": checksum}
                    for name, checksum in camera_hashes.items()},
        "driver_actor_id": driver, "door_operator_actor_id": driver,
        "door": {"side": review["observed_door_side"],
                 "source_ref": "door-pixel-review.json#observed_door_side"},
        "passing_vehicle": {"actor_id": passing,
            "source_ref": "native-door-trace.jsonl#passing_actor_id",
            "lateral_offsets_m": offsets,
            "transit_frames": list(range(__import__("controller").CASES[config["schedule"]]["pass_start"],
                                         __import__("controller").CASES[config["schedule"]]["pass_start"] + 101))},
        "transfer_events": []}
    for event in events:
        source = dict(event)
        source["source_ref"] = "door-pixel-review.json#transfer_events"
        if source["kind"] == "passenger":
            if config.get("transfer_kind", "passenger") != "passenger":
                raise ValueError("Reviewed transfer differs from selected alternative")
            source["pedestrian_actor_id"] = trace[0].get("pedestrian_actor_id")
            source["occupancy_delta"] = source["occupancy_delta_observed"]
        else:
            if config.get("transfer_kind") != "cargo" or \
                    source["cargo_actor_id_observed"] != trace[0].get("cargo_actor_id"):
                raise ValueError("Reviewed cargo differs from original Native actor")
            source["cargo_actor_id"] = source["cargo_actor_id_observed"]
        packet["transfer_events"].append(source)
    measured = measure(packet)
    measured["traffic_rows"], measured["interference_diagnostics"] = interference_rows(trace, states, review, config, measured)
    recording_evidence = derived_channels(attempt, config, frame_rows, trace, packet, measured)
    from worker_exchange.native_output import write_result
    result = {"case_id": config["case_id"],
        "measured_values": {"open_duration_s": measured["open_duration_s"],
                            "post_transfer_open_s": measured["post_transfer_open_s"],
                            "interference_diagnostics": measured["interference_diagnostics"]},
        "target_checks": [{"target": "observed traffic-side door open duration",
            "requested": config.get("schedule"),
            "measured": measured["open_duration_s"],
            "method": "independently reviewed source camera frames joined to Native time",
            "tolerance": None, "matched": None,
            "physical_cause_confirmed": False,
            "cause_evidence": ["door-pixel-review.json", "native-door-trace.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved exact window measured; physical and legal review separate",
        "physical_failure_flags": ["original_physical_completion_review_required"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in VIEWS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": recording_evidence,
        "realized_observables": {"open_duration_s": {
            "value": measured["open_duration_s"], "unit": "s", "statistic": "interval",
            "method": "reviewed pixels with original Native frame/time join",
            "time_window": "600 original frames", "sample_window_s": [0, 599 / 20],
            "reference": "channels/sig.door_open.jsonl"}},
        "legal_verdict_claimed": False, "physical_acceptance_claimed": False}
    write_result(attempt, result)
    report = {"format": "c228817-door-saved-analysis-v1",
        "case_id": config["case_id"],
        "measurements": {"interference_context": {"value": measured["interference_diagnostics"],
                         "method": "interference_rows",
                         "sources": {name: digest(required(attempt, name)) for name in
                             ("native-door-trace.jsonl", "video_frames.jsonl", "door-pixel-review.json", "original-road.json")}},
                         "door_open_duration": measure_open_duration(attempt, measured),
                         "traffic_side_orientation": measure_traffic_side(attempt, measured),
                         "passenger_or_cargo_transfer": measure_transfer(attempt, measured),
                         "interference_window": measure_interference_context(attempt, measured)},
        "measured": measured,
        "original_source_hashes": {name: digest(required(attempt, name)) for name in (
            "native-door-trace.jsonl", "video_frames.jsonl", "door-pixel-review.json",
            "original-scene-review.json", "original-map.json", "original-road.json",
            "original-transfer.json")},
        "camera_sha256": camera_hashes,
        "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
