"""Acquire source-bound original school crossing-zone motion and four camera streams."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess

from school_scene_construction import ASSIGNMENT, load_case
from school_uturn import SOURCES, validate_scene

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
FRAMES = 900
RATE = 20
CONTEXT_SOURCES = SOURCES
CASE_FIELDS = ("children_present", "school_session", "operation_window",
               "beacon_operational", "beacon_flashing", "sign_limit_active")


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
    for key in ("vehicle_xy", "vehicle_heading_deg", "travel_direction",
                "children_xy", "vehicle_speed_mps"):
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
    require(site.get("_source_sha256") == site_sha256, "reviewed school-zone site seal changed")
    output = Path(output)
    require(not output.exists() or not any(output.iterdir()), "original attempt output already populated")
    output.mkdir(parents=True, exist_ok=True)
    context = adapter.read_original_context(site, case)
    require(isinstance(context, dict), "original school-zone context readback missing")
    for key in CONTEXT_SOURCES:
        require(context.get(key + "_source_sha256") == site[key + "_source_sha256"],
                "original context source missing: " + key)
    for key in CASE_FIELDS:
        require(context.get(key) is getattr(case, key),
                "original school-zone intervention mismatch: " + key)
    require(context.get("case_id") == case_id and
            context.get("crossing_zone_rect_m") == site["crossing_zone_rect_m"],
            "original school-zone geometry/source identity mismatch")
    require(context.get("map_sha256") == site.get("map_sha256"),
            "original loaded map differs from reviewed school-zone source")
    validate_scene(context, case)
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
                require(row.get("original_frame") == native_frame and
                        row.get("driver_id") == site["driver_id"] and
                        row.get("vehicle_id") == site["vehicle_id"],
                        "original school-zone identity differs")
                for key in CASE_FIELDS:
                    require(row.get(key) is getattr(case, key),
                            "original school-zone frame intervention differs: " + key)
                for key in SOURCES:
                    require(row.get(key + "_source_sha256") == site[key + "_source_sha256"],
                            "original school-zone frame source differs: " + key)
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
