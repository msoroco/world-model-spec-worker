"""Source-gated Native posted-speed capture using a supplied CARLA adapter.

The adapter owns simulator calls. This module owns exact case, source, frame,
camera, controller and teardown contracts before saved-only processing.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

from posted_control import command, target_speed
from posted_site import load


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def capture(adapter, config: dict, site_path: Path, site_sha256: str, output: Path) -> dict:
    case_id = config["selected_case_id"]
    site = load(site_path, site_sha256, case_id)
    output = Path(output).resolve()
    if not (output / "construction.json").is_file() or (output / "original-attempt").exists():
        raise ValueError("materialized unused exact attempt required")
    original = output / "original-attempt"
    original.mkdir()
    shutil.copy2(site_path, original / "site.json")
    if sha(original / "site.json") != site_sha256:
        raise ValueError("reviewed site changed during capture")
    variables = config["case"]["draft_variables"]
    target = target_speed(site, variables)
    gain = config["control"]["tracking_gain"]
    lane_id = site["travel_lanes"][variables["travel_direction"]]
    owned = []
    frames, motion, route, traces, mappings, video_rows = [], [], [], [], [], []
    restored = False
    try:
        adapter.setup(config, site)
        ego = adapter.spawn_ego(lane_id, config)
        owned.append(ego)
        cameras = adapter.attach_cameras(ego, config["cameras"])
        if set(cameras) != set(VIEWS):
            raise ValueError("four original cameras absent")
        actual = 0.0
        first_frame = None
        for index in range(900):
            throttle, brake = command(actual, target, gain)
            adapter.apply_control(ego, throttle, brake)
            sample = adapter.tick_and_read(ego, cameras)
            frame, time = sample.get("frame"), sample.get("time_s")
            if first_frame is None:
                first_frame = frame
            if type(frame) is not int or frame != first_frame + index or \
                    type(time) not in (int, float) or abs(time - index / 20) > .005:
                raise ValueError("original frame/time gap")
            speed = sample.get("speed_mps")
            if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
                raise ValueError("original vehicle speed invalid")
            actual = speed
            if set(sample.get("camera_png", {})) != set(VIEWS) or any(
                    not isinstance(sample["camera_png"][name], bytes) or
                    not sample["camera_png"][name].startswith(b"\x89PNG\r\n\x1a\n")
                    for name in VIEWS):
                raise ValueError("original synchronized camera frame missing")
            direction = sample.get("direction")
            if not all(isinstance(sample.get(key), str) and sample[key] for key in
                       ("road_id", "segment_id", "direction")) or \
                    type(sample.get("on_highway")) is not bool or \
                    type(sample.get("operating")) is not bool:
                raise ValueError("original route occupancy missing")
            trace = sample.get("trace")
            video = sample.get("video_frame")
            if not isinstance(trace, dict) or trace.get("frame") != frame or \
                    trace.get("time_s") != time or not isinstance(video, dict) or \
                    video.get("carla_frame") != frame or video.get("time_s") != time:
                raise ValueError("original trace/video frame join missing")
            frames.append({"frame": frame, "time_s": time,
                           "camera_sha256": {name: hashlib.sha256(sample["camera_png"][name]).hexdigest()
                                             for name in VIEWS}})
            motion.append({"frame": frame, "time_s": time,
                           "vehicle_id": site["vehicle_id"], "speed_mps": speed})
            route.append({"frame": frame, "time_s": time, "road_id": sample["road_id"],
                          "segment_id": sample["segment_id"], "direction": direction,
                          "on_highway": sample["on_highway"], "operating": sample["operating"]})
            traces.append(trace)
            video_rows.append(video)
            mappings.append({"video_frame": index, "carla_frame": frame, "time_s": time})
        media = adapter.finalize_media(output, VIEWS, tuple(mappings))
        if set(media) != set(VIEWS) | {"raw"} or any(
                Path(media[name]).resolve() != (output / (name + ".mkv")).resolve() or
                not Path(media[name]).is_file() or Path(media[name]).stat().st_size == 0
                for name in media):
            raise ValueError("original encoded media incomplete")
    finally:
        for actor in reversed(owned):
            adapter.destroy(actor)
        restored = adapter.close() is True
    if not restored or len(frames) != 900:
        raise ValueError("original capture or simulator restoration incomplete")
    control = {key: site[key] for key in (
        "case_id", "rate", "unit", "vehicle_id", "highway_dedication_source",
        "public_access_source", "narrow_road_geometry_source", "vehicle_clearance_source",
        "governed_segment_source", "governed_direction_source", "sign_position_source",
        "posting_authority_source", "public_authority_posted", "sign_in_camera_view",
        "governed_road_id", "governed_segment_id", "governed_direction")}
    control["source_kind"] = "original_native_context"
    if "off_camera_reading_assumption_source" in site:
        control["off_camera_reading_assumption_source"] = site["off_camera_reading_assumption_source"]
    packets = {"frame_map": {"frames": frames},
               "vehicle_motion": {"case_id": case_id, "source_kind": "original_native", "samples": motion},
               "route_occupancy": {"case_id": case_id, "source_kind": "original_native", "samples": route},
               "posted_control": control}
    sources = {}
    for name, packet in packets.items():
        path = original / (name + ".json")
        write(path, packet)
        sources[name] = {"path": path.name, "sha256": sha(path)}
    (output / "trace.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in traces))
    (output / "video_frames.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in video_rows))
    media_inventory = {}
    for name in VIEWS:
        shutil.copy2(output / (name + ".mkv"), original / (name + ".mkv"))
        media_inventory[name] = {"path": name + ".mkv", "sha256": sha(original / (name + ".mkv"))}
    shutil.copy2(output / "trace.jsonl", original / "trace.jsonl")
    media_inventory["trace"] = {"path": "trace.jsonl", "sha256": sha(original / "trace.jsonl")}
    write(original / "inventory.json", {"case_id": case_id, "source_kind": "original_native",
                                        "sources": sources, "media": media_inventory,
                                        "diagnostic_fixture": False})
    write(original / "posted-speed-source.json", {"case_id": case_id,
                                                   "source_kind": "original_native",
                                                   "diagnostic_fixture": False})
    sealed = {str(path.relative_to(output)): sha(path) for path in output.rglob("*") if path.is_file()}
    write(output / "capture-seal.json", {
        "events": ["capture_finished", "encoders_closed", "restoration_verified"],
        "sources": sealed,
        "native_revision": {"construction_sha256": sha(output / "construction.json"),
                            "runner_sha256": sha(output / "runner.py")}})
    return {"case_id": case_id, "frame_count": 900,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
