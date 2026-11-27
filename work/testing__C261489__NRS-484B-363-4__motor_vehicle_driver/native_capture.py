"""Acquire original synchronized school pass telemetry and four camera streams."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess

from school_pass import ASSIGNMENT, SOURCES, measure_original, validate_scene


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
FRAMES = 900
RATE = 20


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def validate_frame(row: dict, index: int, native_frame: int, t0: float) -> None:
    require(type(row) is dict and row.get("original_frame") == native_frame and
            row.get("frame") == index and row.get("native_frame") == native_frame,
            "original frame identity differs from Native tick")
    elapsed = row.get("time_s")
    require(type(elapsed) in (int, float) and math.isfinite(elapsed) and
            abs(elapsed - index / RATE) <= .002 and math.isfinite(t0),
            "original frame cadence mismatch")
    for key in ("ego_id", "target_id", "driver_id", "ego_xy", "target_xy",
                "ego_route_progress_m", "target_route_progress_m", "lateral_separation_m",
                "ego_actor_id", "target_actor_id", "ego_body_vertices_m",
                "target_body_vertices_m", "ego_vehicle_blueprint", "target_vehicle_blueprint"):
        require(key in row, "original two-vehicle readback missing: " + key)
    require(type(row["ego_actor_id"]) is int and type(row["target_actor_id"]) is int and
            row["ego_actor_id"] != row["target_actor_id"] and
            row["ego_vehicle_blueprint"].startswith("vehicle.") and
            row["target_vehicle_blueprint"].startswith("vehicle."),
            "original conventional vehicles not retained")
    for name in ("ego_body_vertices_m", "target_body_vertices_m"):
        vertices = row[name]
        require(isinstance(vertices, list) and len(vertices) >= 4 and
                all(isinstance(vertex, list) and len(vertex) == 3 and
                    all(type(value) in (int, float) and math.isfinite(value) for value in vertex)
                    for vertex in vertices), "original vehicle body geometry missing: " + name)


def encoder(output: Path, view: str):
    width, height = SIZES[view]
    return subprocess.Popen(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
         "-framerate", str(RATE), "-i", "-", "-an", "-c:v", "ffv1", "-threads", "1",
         str(output / (view + ".mkv"))], stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def capture(client, world, adapter, ego, site: dict, case_id: str,
            output: Path, site_sha256: str) -> dict:
    """Tick one Native episode; all observations share the same original frame."""
    from pipeline_capture import PipelineCapture

    require(site.get("_source_sha256") == site_sha256,
            "original reviewed school site seal changed")
    validate_scene(site, case_id)
    output = Path(output)
    require(output.is_dir() and not (output / "original-trace.jsonl").exists(),
            "original attempt already has a source trace")
    context = adapter.read_original_context(site, case_id)
    require(isinstance(context, dict) and context.get("case_id") == case_id and
            context.get("map_sha256") == site.get("map_sha256"),
            "original context or map readback differs")
    for name in SOURCES:
        require(context.get(name + "_source_sha256") == site[name + "_source_sha256"],
                "original context source differs: " + name)
    validate_scene(context, case_id)
    context["site_sha256"] = site_sha256
    context["duration_frames"] = FRAMES
    context_path = output / "context.json"
    write_json(context_path, context)
    previous = copy.copy(world.get_settings())
    settings = copy.copy(previous)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / RATE
    encoders = {}
    rows = []
    original_path = output / "original-trace.jsonl"
    try:
        world.apply_settings(settings)
        readback = world.get_settings()
        require(readback.synchronous_mode is True and
                abs(readback.fixed_delta_seconds - 1 / RATE) < 1e-9,
                "Native 20 Hz setting readback failed")
        for view in VIEWS:
            encoders[view] = encoder(output, view)
        with PipelineCapture(client, ego, output, case_id) as pipeline:
            t0 = None
            last = None
            with original_path.open("x") as stream:
                for index in range(FRAMES):
                    adapter.control_frame(case_id, index)
                    frame = world.tick()
                    snapshot = world.get_snapshot()
                    now = float(snapshot.timestamp.elapsed_seconds)
                    require(type(frame) is int and snapshot.frame == frame and
                            (last is None or frame == last + 1),
                            "original Native frame discontinuity")
                    if t0 is None:
                        t0 = now
                    require(math.isfinite(now) and abs(now - t0 - index / RATE) <= .005,
                            "original Native time discontinuity")
                    last = frame
                    pipeline.capture(frame, index / RATE)
                    row = adapter.read_original_frame(case_id, index, frame)
                    validate_frame(row, index, frame, t0)
                    require(row["driver_id"] == site["driver_id"] and
                            row["ego_id"] == site["ego_id"] and
                            row["target_id"] == site["target_id"],
                            "original school pass identities changed")
                    for name in SOURCES:
                        require(row.get(name + "_source_sha256") == site[name + "_source_sha256"],
                                "original source changed: " + name)
                    rows.append(row)
                    stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                            allow_nan=False) + "\n")
                    for view in VIEWS:
                        pixels = adapter.camera_rgb24(view, frame)
                        width, height = SIZES[view]
                        require(type(pixels) is bytes and len(pixels) == width * height * 3,
                                "original synchronized RGB pixels missing: " + view)
                        encoders[view].stdin.write(pixels)
        for view, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            require(process.wait(timeout=300) == 0,
                    "original camera encode failed: " + view + ": " + error.decode(errors="replace"))
        measured = measure_original(rows, context, case_id)
        streams = {view: {"path": view + ".mkv", "sha256": sha(output / (view + ".mkv")),
                          "fps": RATE, "frame_count": FRAMES} for view in VIEWS}
        cameras_path = output / "cameras.json"
        write_json(cameras_path, {"assignment_id": ASSIGNMENT, "case_id": case_id,
                                  "fps": RATE, "frame_count": FRAMES, "streams": streams})
        receipt_path = output / "receipt.json"
        write_json(receipt_path, {"assignment_id": ASSIGNMENT, "case_id": case_id,
                                  "source_kind": "original_native_capture", "diagnostic_fixture": False,
                                  "fps": RATE, "frame_count": FRAMES, "site_sha256": site_sha256,
                                  "context_sha256": sha(context_path), "trace_sha256": sha(original_path),
                                  "camera_manifest_sha256": sha(cameras_path),
                                  "measurement": measured})
        return {"context": str(context_path), "trace": str(original_path),
                "cameras": str(cameras_path), "receipt": str(receipt_path)}
    finally:
        for process in encoders.values():
            if process.poll() is None:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                process.terminate()
                process.wait(timeout=30)
        world.apply_settings(previous)
        restored = world.get_settings()
        require(restored.synchronous_mode == previous.synchronous_mode and
                restored.fixed_delta_seconds == previous.fixed_delta_seconds,
                "Native settings restoration readback failed")
