"""Lazy Native operator capture of original curb motion and four camera streams."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

from curb_construction import build_plan
from curb_geometry import load_site, measure_original

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _scratch():
    root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if ".runtime-work" not in root.parts:
        raise ValueError("Native scratch must be under .runtime-work")
    root.mkdir(parents=True, exist_ok=True)
    return root


def capture(operator, site_packet, case_id, destination, *, fallback=False, diagnostic=False,
            diagnostic_full_duration=False,
            after_tick=None):
    """Capture immutable original readback; targets never become observations."""
    destination = Path(destination)
    if destination.exists() and (destination / "original-attempt").exists():
        raise ValueError("refusing to replace original attempt")
    if ".runtime-work" not in destination.resolve().parts:
        raise ValueError("original attempt must be under .runtime-work")
    if after_tick is not None and not callable(after_tick):
        raise ValueError("same-tick capture callback invalid")
    site = load_site(site_packet, case_id)
    plan = build_plan(site_packet, case_id, fallback=fallback)
    map_source = Path(site_packet).parent / site["sources"]["native_opendrive_map"]["path"]
    original_map = operator.get_opendrive_bytes()
    if not isinstance(original_map, bytes) or hashlib.sha256(original_map).hexdigest() != site["sources"]["native_opendrive_map"]["sha256"]:
        raise ValueError("Native OpenDRIVE differs from reviewed original map")
    if diagnostic_full_duration and not diagnostic:
        raise ValueError("full-duration diagnostic requires diagnostic provenance")
    frame_count = 900 if diagnostic_full_duration or not diagnostic else 9
    root = Path(tempfile.mkdtemp(prefix="c214875-native-", dir=_scratch()))
    original = root / "original-attempt"
    original.mkdir()
    archives = {}
    rows, frames = [], []
    started = False
    try:
        shutil.copy2(site_packet, original / "site.json")
        for item in site["sources"].values():
            source = Path(site_packet).parent / item["path"]
            target = original / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        _write(original / "plan.json", plan)
        (original / "road.xodr").write_bytes(original_map)
        operator.start(plan)
        started = True
        actors = operator.read_actor_inventory()
        if not isinstance(actors, dict) or not actors.get("ego_vehicle_id") or not actors.get("actual_blueprint"):
            raise ValueError("original ordinary motor vehicle readback missing")
        _write(original / "actors.json", actors)
        archives = {name: zipfile.ZipFile(original / (name + ".zip"), "w", zipfile.ZIP_STORED)
                    for name in CAMERAS}
        for index in range(frame_count):
            tick = operator.tick()
            native_frame = tick.get("frame")
            native_time = tick.get("time_s")
            if type(native_frame) is not int or type(native_time) not in (int, float) or not math.isfinite(native_time):
                raise ValueError("original Native tick missing")
            if frames and (native_frame != frames[-1]["native_frame"] + 1 or
                           abs(native_time - frames[-1]["native_time_s"] - .05) > .001):
                raise ValueError("original Native frame gap or cadence drift")
            if after_tick is not None:
                after_tick(native_frame, native_time)
            wheels = operator.read_right_wheels(native_frame)
            if (not isinstance(wheels, dict) or wheels.get("frame") != native_frame or
                    wheels.get("time_s") != native_time or wheels.get("source_kind") != "original_native" or
                    wheels.get("ego_vehicle_id") != actors["ego_vehicle_id"]):
                raise ValueError("original right-wheel actor or tick identity differs")
            speed = wheels.get("speed_mps")
            if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
                raise ValueError("original vehicle speed missing")
            parking_brake = wheels.get("parking_brake_applied")
            if type(parking_brake) is not bool:
                raise ValueError("original parking control readback missing")
            from curb_geometry import measure_right_wheels
            measure_right_wheels(wheels.get("right_front_wheel_xy_m"),
                                 wheels.get("right_rear_wheel_xy_m"), site["right_curb_xy_m"])
            cameras = operator.read_cameras(native_frame)
            if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
                raise ValueError("four original cameras missing")
            for name in CAMERAS:
                packet = cameras[name]
                png = packet.get("png")
                if (packet.get("frame") != native_frame or packet.get("time_s") != native_time or
                        not isinstance(png, bytes) or not png.startswith(b"\x89PNG\r\n\x1a\n")):
                    raise ValueError("original camera frame missing: " + name)
                archives[name].writestr(f"{index:04d}-{native_frame}.png", png)
            rows.append({"case_id": case_id, "frame": index, "native_frame": native_frame,
                         "time_s": native_time, "speed_mps": speed,
                         "parking_brake_applied": parking_brake,
                         "right_front_wheel_xy_m": wheels["right_front_wheel_xy_m"],
                         "right_rear_wheel_xy_m": wheels["right_rear_wheel_xy_m"]})
            frames.append({"frame": index, "native_frame": native_frame, "native_time_s": native_time})
        if hashlib.sha256(operator.get_opendrive_bytes()).hexdigest() != hashlib.sha256(map_source.read_bytes()).hexdigest():
            raise ValueError("Native map changed during original capture")
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    finally:
        for archive in archives.values():
            archive.close()
        try:
            graph = getattr(operator, "pipeline_capture", None)
            if graph is not None:
                graph.close(confirmed=len(rows) == frame_count)
        finally:
            if started:
                try:
                    operator.brake()
                finally:
                    operator.cleanup()
                    operator.capture_cleanup_complete = True
    try:
        motion = original / "wheel-motion.jsonl"
        motion.write_text("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n")
        _write(original / "wheel-seal.json", {
            "case_id": case_id, "frame_count": frame_count,
            "motion_sha256": hashlib.sha256(motion.read_bytes()).hexdigest(),
            "site_sha256": hashlib.sha256((original / "site.json").read_bytes()).hexdigest()})
        _write(original / "frame-map.json", {"case_id": case_id, "frames": frames})
        measured = measure_original(root, case_id, diagnostic=diagnostic)
        _write(original / "measurement.json", measured)
        _write(original / "inventory.json", {
            "case_id": case_id, "frame_count": frame_count, "rate_hz": 20,
            "source_kind": "original_native", "diagnostic_fixture": diagnostic,
            "physical_completion": False,
            "source_sha256": {name: hashlib.sha256((original / name).read_bytes()).hexdigest()
                              for name in ("site.json", "plan.json", "actors.json", "road.xodr",
                                           "wheel-motion.jsonl", "wheel-seal.json", "frame-map.json",
                                           "measurement.json")},
            "camera_sha256": {name: hashlib.sha256((original / (name + ".zip")).read_bytes()).hexdigest()
                              for name in CAMERAS}})
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            os.replace(original, destination / "original-attempt")
            shutil.rmtree(root)
        else:
            os.replace(root, destination)
        return measured
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
