"""Acquire source-bound original yield motion and synchronized four-view video."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess

from yield_view_measurement import ASSIGNMENT
from yield_scene_construction import VARIANTS

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
FRAMES = 900
RATE = 20
SOURCE_FIELDS = ("map_source_sha256", "yield_sign_survey_sha256",
                 "marking_survey_sha256", "view_ray_survey_sha256",
                 "through_highway_survey_sha256")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False) + "\n")


def _encoder(output, view):
    width, height = SIZES[view]
    return subprocess.Popen(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
         "-framerate", str(RATE), "-i", "-", "-an", "-c:v", "ffv1", "-threads", "1",
         str(output / (view + ".mkv"))], stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _validate_row(row, index, native_frame, site, case_id):
    require(isinstance(row, dict) and row.get("frame") == index and
            row.get("native_frame") == native_frame and
            row.get("original_frame") == native_frame and
            type(row.get("time_s")) in (int, float) and
            math.isfinite(row["time_s"]) and abs(row["time_s"] - index / RATE) <= .002,
            "original Native frame/time join differs")
    for name in ("actor_id", "vehicle_blueprint", "position_m", "heading_xy",
                 "body_vertices_m", "ego_speed_mps", "ego_within_intersection",
                 "distance_to_intersection_m", "through_vehicle_ids", "through_vehicles"):
        require(name in row, "original yield motion field missing: " + name)
    require(type(row["actor_id"]) is int and row["actor_id"] > 0 and
            isinstance(row["vehicle_blueprint"], str) and
            row["vehicle_blueprint"].startswith("vehicle."),
            "original motor vehicle identity missing")
    for name, length in (("position_m", 3), ("heading_xy", 2)):
        values = row[name]
        require(isinstance(values, list) and len(values) == length and
                all(type(value) in (int, float) and math.isfinite(value) for value in values),
                "original Native geometry differs: " + name)
    require(isinstance(row["body_vertices_m"], list) and len(row["body_vertices_m"]) >= 4 and
            all(isinstance(vertex, list) and len(vertex) == 3 and
                all(type(value) in (int, float) and math.isfinite(value) for value in vertex)
                for vertex in row["body_vertices_m"]), "original body geometry missing")
    require(type(row["ego_within_intersection"]) is bool and
            type(row["ego_speed_mps"]) in (int, float) and row["ego_speed_mps"] >= 0 and
            isinstance(row["through_vehicle_ids"], list) and
            isinstance(row["through_vehicles"], list), "original yield/through observation missing")
    require(row.get("case_id") == case_id and
            row.get("control") == "yield_sign" and
            row.get("stop_line_present") is False and
            row.get("near_crosswalk_present") is False,
            "original yield branch intervention differs")
    for key in SOURCE_FIELDS:
        require(row.get(key) == site[key], "original site source changed: " + key)


def capture(world, adapter, site, case_id, output, site_sha256):
    require(site.get("_source_sha256") == site_sha256,
            "reviewed yield site source changed")
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    require(suffix in VARIANTS, "unknown selected yield case")
    output = Path(output)
    require(not output.exists() or not any(output.iterdir()),
            "original attempt output already populated")
    output.mkdir(parents=True, exist_ok=True)
    context = adapter.read_original_context(site, case_id)
    require(isinstance(context, dict) and context.get("case_id") == case_id and
            context.get("assignment_id") == ASSIGNMENT and
            context.get("source_kind") == "original_native_readback" and
            context.get("control") == "yield_sign" and
            context.get("stop_line_present") is False and
            context.get("near_crosswalk_present") is False and
            context.get("sidewalk_derived_crosswalk_present") is False and
            context.get("police_control_active") is False and
            context.get("traffic_signal_control_active") is False,
            "original governed yield/no-line/no-crosswalk readback missing")
    for key in SOURCE_FIELDS:
        require(context.get(key) == site[key], "original source differs: " + key)
    require(isinstance(context.get("source_recording_id"), str) and
            bool(context["source_recording_id"]) and
            isinstance(context.get("approach_view_stations"), list) and
            bool(context["approach_view_stations"]),
            "original recording identity and view-ray stations required")
    context["yield_sign_source_sha256"] = site["yield_sign_survey_sha256"]
    context["view_ray_source_sha256"] = site["view_ray_survey_sha256"]
    context["site_sha256"] = site_sha256
    context["duration_frames"] = FRAMES
    context["planned_ego_response"], context["planned_through_traffic_phase"] = VARIANTS[suffix]
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
                adapter.control_frame(case_id, index)
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
                row = adapter.read_original_frame(case_id, index, native_frame)
                _validate_row(row, index, native_frame, site, case_id)
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
