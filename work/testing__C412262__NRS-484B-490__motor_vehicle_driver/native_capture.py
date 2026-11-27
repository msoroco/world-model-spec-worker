"""Acquire source-bound original highway parking motion and four camera streams."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess

from highway_scene_construction import ASSIGNMENT, SOURCE_FIELDS, load_case

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
FRAMES = 900
RATE = 20
CONTEXT_SOURCES = (
    "highway_dedication_source", "highway_boundary_source", "public_access_source",
    "full_width_survey_source", "device_erection_source", "device_authority_source",
    "device_exact_content_source", "device_conformity_source", "device_extent_source",
    "person_identity_source", "vehicle_identity_source", "parking_purpose_source",
    "service_activity_source")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False) + "\n")


def validate_frame(row, index, native_frame, origin_time):
    require(isinstance(row, dict) and row.get("native_frame") == native_frame,
            "original frame identity differs from Native tick")
    require(row.get("frame") == index and
            isinstance(row.get("time_s"), (int, float)) and
            not isinstance(row.get("time_s"), bool) and
            math.isfinite(row["time_s"]) and abs(row["time_s"] - index / RATE) <= .002,
            "original frame cadence mismatch")
    for key in ("vehicle_center_xy_m", "vehicle_body_polygon_xy_m", "vehicle_speed_mps"):
        require(key in row, "original vehicle motion field missing: " + key)
    for key in ("actor_id", "vehicle_blueprint", "position_m", "heading_xy",
                "body_vertices_m"):
        require(key in row, "original Native actor readback missing: " + key)
    require(type(row["actor_id"]) is int and row["actor_id"] > 0 and
            isinstance(row["vehicle_blueprint"], str) and
            row["vehicle_blueprint"].startswith("vehicle."),
            "original motor vehicle identity invalid")
    for key, count in (("position_m", 3), ("heading_xy", 2)):
        values = row[key]
        require(isinstance(values, list) and len(values) == count and
                all(type(value) in (int, float) and math.isfinite(value) for value in values),
                "original Native position or heading invalid: " + key)
    require(isinstance(row["body_vertices_m"], list) and len(row["body_vertices_m"]) >= 4 and
            all(isinstance(vertex, list) and len(vertex) == 3 and
                all(type(value) in (int, float) and math.isfinite(value) for value in vertex)
                for vertex in row["body_vertices_m"]),
            "original motor vehicle body vertices invalid")
    require(isinstance(origin_time, (int, float)) and math.isfinite(origin_time),
            "Native snapshot timestamp unavailable")


def _encoder(output: Path, view: str):
    width, height = SIZES[view]
    return subprocess.Popen(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
         "-framerate", str(RATE), "-i", "-", "-an", "-c:v", "ffv1", "-threads", "1",
         str(output / (view + ".mkv"))], stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def capture(world, adapter, site, case_id: str, output: Path, site_sha256: str) -> dict:
    case = load_case(case_id)
    require(site.get("_source_sha256") == site_sha256, "reviewed highway site seal changed")
    output = Path(output)
    require(not output.exists() or not any(output.iterdir()), "original attempt output already populated")
    output.mkdir(parents=True, exist_ok=True)
    context = adapter.read_original_context(site, case)
    require(isinstance(context, dict), "original highway context readback missing")
    for key in CONTEXT_SOURCES:
        require(context.get(key), "original context source missing: " + key)
    for key, expected in (("highway_width_request", case["highway_width_request"]),
                          ("device_request", case["device_request"]),
                          ("activity_request", case["activity_request"]),
                          ("parking_location_request", case["parking_location_request"])):
        require(context.get(key) == expected, "original context intervention mismatch: " + key)
    require(context.get("assignment_id") == ASSIGNMENT and
            context.get("source_kind") == "original_reviewed_highway_site" and
            context.get("case_id") == case_id and
            context.get("highway_boundary_xy_m") == site["highway_boundary_xy_m"] and
            context.get("full_highway_width_profile_m") == site["full_highway_width_profile_m"],
            "original highway geometry/source identity mismatch")
    for key in SOURCE_FIELDS:
        require(context.get(key) == site.get(key), "reviewed original source seal differs: " + key)
    require(context.get("map_sha256") == site.get("map_sha256"),
            "original loaded map differs from reviewed highway source")
    context["site_sha256"] = site_sha256
    context["camera_plan_sha256"] = sha(Path(__file__).resolve().parent / "config.json")
    context["duration_frames"] = FRAMES
    context_path = output / "context.json"
    write_json(context_path, context)
    prior = copy.copy(world.get_settings())
    settings = copy.copy(prior)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / RATE
    encoders = {}
    trace_path = output / "original-trace.jsonl"
    try:
        world.apply_settings(settings)
        current = world.get_settings()
        require(current.synchronous_mode is True and
                abs(current.fixed_delta_seconds - 1 / RATE) < 1e-9,
                "Native 20 Hz settings readback failed")
        for view in VIEWS:
            encoders[view] = _encoder(output, view)
        start_time = last_frame = None
        with trace_path.open("w") as trace:
            for index in range(FRAMES):
                adapter.control_frame(case, index)
                native_frame = world.tick()
                snapshot = world.get_snapshot()
                now = float(snapshot.timestamp.elapsed_seconds)
                require(type(native_frame) is int and snapshot.frame == native_frame and
                        (last_frame is None or native_frame == last_frame + 1),
                        "Native frame identity discontinuity")
                if start_time is None:
                    start_time = now
                require(math.isfinite(now) and abs(now - start_time - index / RATE) <= .005,
                        "Native timestamp discontinuity")
                last_frame = native_frame
                row = adapter.read_original_frame(case, index, native_frame)
                validate_frame(row, index, native_frame, now)
                trace.write(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                       allow_nan=False) + "\n")
                for view in VIEWS:
                    pixels = adapter.camera_rgb24(view, native_frame)
                    width, height = SIZES[view]
                    require(type(pixels) is bytes and len(pixels) == width * height * 3,
                            "original synchronized RGB frame missing: " + view)
                    encoders[view].stdin.write(pixels)
        for view, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            require(process.wait(timeout=300) == 0,
                    "original camera encode failed: " + view + ": " + error.decode(errors="replace"))
        streams = {view: {"path": view + ".mkv", "sha256": sha(output / (view + ".mkv")),
                          "fps": RATE, "frame_count": FRAMES} for view in VIEWS}
        camera_manifest = output / "cameras.json"
        write_json(camera_manifest, {"assignment_id": ASSIGNMENT, "case_id": case_id,
                                      "fps": RATE, "frame_count": FRAMES, "streams": streams})
        receipt = output / "receipt.json"
        write_json(receipt, {"assignment_id": ASSIGNMENT, "case_id": case_id,
                             "source_kind": "original_native_capture", "diagnostic_fixture": False,
                             "fps": RATE, "frame_count": FRAMES,
                             "context_sha256": sha(context_path), "trace_sha256": sha(trace_path),
                             "camera_manifest_sha256": sha(camera_manifest),
                             "site_sha256": site_sha256})
        return {"context": str(context_path), "trace": str(trace_path),
                "camera_manifest": str(camera_manifest), "receipt": str(receipt)}
    finally:
        for process in encoders.values():
            if process.poll() is None:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                process.terminate()
                process.wait(timeout=30)
        world.apply_settings(prior)
        restored = world.get_settings()
        require(restored.synchronous_mode == prior.synchronous_mode and
                restored.fixed_delta_seconds == prior.fixed_delta_seconds,
                "Native settings restoration readback failed")
