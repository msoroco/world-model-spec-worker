"""Saved-only door measurement from original capture and separately reviewed pixels.

Actuator requests are never used as observations. The review file must be
authored after inspecting the four original camera streams.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from measure_door import FRAME_COUNT, VIEWS, measure


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
    observations = review.get("door_observations")
    if not isinstance(observations, list) or len(observations) != frame_count:
        raise ValueError("Every original frame needs reviewed door state")
    for i, row in enumerate(observations):
        if row.get("video_frame") != i or type(row.get("door_open")) is not bool:
            raise ValueError("Incomplete reviewed door frame")
        if row.get("source_camera") not in VIEWS or not row.get("pixel_box_xyxy"):
            raise ValueError("Door state needs reviewed source pixels")
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
            "transit_frames": list(range(110, 211))},
        "transfer_events": []}
    for event in events:
        source = dict(event)
        source["source_ref"] = "door-pixel-review.json#transfer_events"
        if source["kind"] == "passenger":
            source["pedestrian_actor_id"] = trace[0].get("pedestrian_actor_id")
            source["occupancy_delta"] = source["occupancy_delta_observed"]
        else:
            source["cargo_actor_id"] = source["cargo_actor_id_observed"]
        packet["transfer_events"].append(source)
    measured = measure(packet)
    report = {"format": "c228817-door-saved-analysis-v1",
        "case_id": config["case_id"],
        "measurements": {"door_open_duration": measure_open_duration(attempt, measured)},
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
