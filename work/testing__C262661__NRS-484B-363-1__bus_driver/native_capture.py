"""Capture original 20 Hz bus, zone and beacon readbacks with four RGB views."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess

from school_scene_construction import ASSIGNMENT, SOURCES, load_case

FRAMES = 900
RATE = 20
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False) + "\n")


def validate_frame(row, index, native_frame, case, site):
    require(isinstance(row, dict) and row.get("native_frame") == native_frame and
            row.get("frame") == index and type(row.get("time_s")) in (int, float) and
            math.isfinite(row["time_s"]) and abs(row["time_s"] - index / RATE) <= .002,
            "original Native frame identity/cadence differs")
    require(row.get("map_sha256") == site["map_sha256"] and
            row.get("driver_id") == site["driver_id"] and
            row.get("vehicle_id") == site["vehicle_id"],
            "original Native map, driver or bus identity differs")
    require(row.get("vehicle_blueprint") ==
            (site["bus_blueprint"] if case["vehicle_request"] == "motor_bus" else site.get("car_blueprint")),
            "original vehicle blueprint differs")
    require(type(row.get("bus_speed_mps")) in (int, float) and
            math.isfinite(row["bus_speed_mps"]) and row["bus_speed_mps"] >= 0,
            "original Native speed missing")
    require(type(row.get("inside_designated_zone")) is bool and
            type(row.get("sign_limit_active")) is bool,
            "original zone or sign readback missing")
    lights = row.get("beacon_yellow_lights_lit")
    require(isinstance(lights, list) and len(lights) == site["beacon_yellow_lamp_count"] and
            all(type(value) is bool for value in lights),
            "original per-yellow-lamp readback missing")
    children = row.get("children_actor_ids")
    require(isinstance(children, list) and all(isinstance(value, str) and value for value in children),
            "original child actor inventory missing")
    children_readback = row.get("children_actor_readback")
    require(isinstance(children_readback, list) and
            {str(child.get("actor_id")) for child in children_readback if isinstance(child, dict)} ==
                set(children), "original child actor body readback missing")
    for child in children_readback:
        require(type(child.get("actor_id")) is int and child["actor_id"] > 0 and
                isinstance(child.get("blueprint"), str) and
                isinstance(child.get("position_m"), list) and len(child["position_m"]) == 3 and
                isinstance(child.get("body_vertices_m"), list) and
                len(child["body_vertices_m"]) >= 4,
                "original child body and blueprint readback incomplete")
    require(type(row.get("actor_id")) is int and row["actor_id"] > 0 and
            isinstance(row.get("position_m"), list) and len(row["position_m"]) == 3 and
            isinstance(row.get("heading_xy"), list) and len(row["heading_xy"]) == 2 and
            isinstance(row.get("body_vertices_m"), list) and len(row["body_vertices_m"]) >= 4,
            "original bus body/heading readback missing")
    require(row.get("school_in_session_today") is site["school_in_session_today"] and
            row.get("beacon_or_sign_state") == case["beacon_or_sign_request"] and
            row.get("time_window_label") == case["time_request"],
            "original school/device intervention readback differs")
    for name in SOURCES:
        require(row.get(name + "_source_sha256") == site[name + "_source_sha256"],
                "original school source changed during capture: " + name)


def _encoder(output, view):
    width, height = SIZES[view]
    return subprocess.Popen(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
         "-framerate", str(RATE), "-i", "-", "-an", "-c:v", "ffv1", "-threads", "1",
         str(output / (view + ".mkv"))], stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def capture(world, adapter, site, case_id, output, site_sha256):
    case = load_case(case_id)
    require(site.get("_source_sha256") == site_sha256,
            "reviewed original school-zone site seal changed")
    output = Path(output)
    require(not output.exists() or not any(output.iterdir()),
            "original attempt output already populated")
    output.mkdir(parents=True, exist_ok=True)
    context = adapter.read_original_context(site, case)
    require(isinstance(context, dict) and context.get("case_id") == case_id and
            context.get("map_sha256") == site["map_sha256"],
            "original site/map context readback missing")
    require(context.get("vehicle_id") == site["vehicle_id"] and
            context.get("driver_id") == site["driver_id"] and
            context.get("bus_blueprint") == site["bus_blueprint"] and
            context.get("vehicle_blueprint") ==
                (site["bus_blueprint"] if case["vehicle_request"] == "motor_bus" else site.get("car_blueprint")) and
            context.get("zone_polygon_xy_m") == site["zone_polygon_xy_m"] and
            context.get("route_xy_m") == site["route_xy_m"],
            "original bus identity, zone or route context readback differs")
    require(context.get("school_in_session_today") is site["school_in_session_today"] and
            context.get("operational_beacon_designation") is site["operational_beacon_designation"],
            "original calendar/beacon designation readback differs")
    for field in ("local_datetime", "operation_end_local", "next_operation_start_local",
                  "class_start_local", "class_end_local"):
        require(context.get(field) == site["timing_packet"].get(field),
                "original independent school clock readback differs: " + field)
    for name in SOURCES:
        require(context.get(name + "_source_sha256") == site[name + "_source_sha256"] and
                context.get(name + "_source"),
                "original independent context source missing: " + name)
    context["site_sha256"] = site_sha256
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
        applied = world.get_settings()
        require(applied.synchronous_mode is True and
                abs(applied.fixed_delta_seconds - 1 / RATE) < 1e-9,
                "original Native 20 Hz settings readback failed")
        for view in VIEWS:
            encoders[view] = _encoder(output, view)
        first_time = last_frame = None
        with trace_path.open("x") as stream:
            for index in range(FRAMES):
                adapter.control_frame(case, index)
                number = world.tick()
                snapshot = world.get_snapshot()
                now = float(snapshot.timestamp.elapsed_seconds)
                require(type(number) is int and snapshot.frame == number and
                        (last_frame is None or number == last_frame + 1),
                        "original Native tick discontinuity")
                if first_time is None:
                    first_time = now
                require(math.isfinite(now) and abs(now - first_time - index / RATE) <= .005,
                        "original Native timestamp discontinuity")
                last_frame = number
                row = adapter.read_original_frame(case, index, number)
                validate_frame(row, index, number, case, site)
                stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                        allow_nan=False) + "\n")
                for view in VIEWS:
                    pixels = adapter.camera_rgb24(view, number)
                    width, height = SIZES[view]
                    require(type(pixels) is bytes and len(pixels) == width * height * 3,
                            "original synchronized RGB callback missing: " + view)
                    encoders[view].stdin.write(pixels)
        for view, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            require(process.wait(timeout=300) == 0,
                    "original camera encode failed: " + view + ": " + error.decode(errors="replace"))
        streams = {view: {"path": view + ".mkv", "sha256": sha(output / (view + ".mkv")),
                          "fps": RATE, "frame_count": FRAMES} for view in VIEWS}
        camera_path = output / "cameras.json"
        write_json(camera_path, {"assignment_id": ASSIGNMENT, "case_id": case_id,
                                 "fps": RATE, "frame_count": FRAMES, "streams": streams})
        receipt_path = output / "receipt.json"
        write_json(receipt_path, {"assignment_id": ASSIGNMENT, "case_id": case_id,
                                  "source_kind": "original_native_capture", "diagnostic_fixture": False,
                                  "fps": RATE, "frame_count": FRAMES,
                                  "context_sha256": sha(context_path), "trace_sha256": sha(trace_path),
                                  "camera_manifest_sha256": sha(camera_path),
                                  "site_sha256": site_sha256})
        return {"context": str(context_path), "trace": str(trace_path),
                "camera_manifest": str(camera_path), "receipt": str(receipt_path)}
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
                "original Native world settings restoration readback failed")
