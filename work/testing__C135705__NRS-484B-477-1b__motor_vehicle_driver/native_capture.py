"""Acquire original width evidence from a source-hashed Native alley operator.

The operator supplies actual map/actor readback and original frames. Requested
parking widths and other-vehicle positions are never used as observed values.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

from alley_width_construction import VARIANTS, build_plan
from width_measurement import ASSIGNMENT, measure_saved

CAMERAS = frozenset(("overview", "approach", "reference_corner", "driver_reference"))
FRAMES = 900


def _write(path, value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def capture(operator, case_id, output, after_tick=None):
    """Capture via injected operator; fail closed on absent original readback."""
    variant = case_id.removeprefix(ASSIGNMENT + "__")
    if not case_id.startswith(ASSIGNMENT + "__") or variant not in VARIANTS:
        raise ValueError("unknown exact alley-width case")
    destination = Path(output)
    if destination.exists():
        raise ValueError("refusing to replace original attempt")
    if after_tick is not None and not callable(after_tick):
        raise ValueError("same-tick Core graph callback missing")
    geometry = operator.get_map_packet(case_id)
    if geometry.get("case_id") != case_id or geometry.get("source_kind") != "original_native_geometry":
        raise ValueError("original source-gated alley packet missing")
    if geometry.get("alley_kind") != "other_alley" or geometry.get("public_highway_status") is not True:
        raise ValueError("qualifying other alley source review missing")
    if variant == "ordinance_otherwise" and geometry.get("ordinance_status") != "otherwise_provides":
        raise ValueError("reviewed local ordinance exception source missing")
    if not geometry.get("map_sha256") or not geometry.get("ego_blueprint_source") or not geometry.get("ego_dimensions_source"):
        raise ValueError("original map or ego blueprint source missing")
    map_bytes = operator.get_opendrive_bytes()
    if not isinstance(map_bytes, bytes) or hashlib.sha256(map_bytes).hexdigest() != geometry["map_sha256"]:
        raise ValueError("Native map bytes differ from reviewed source")
    plan = build_plan(geometry, case_id, direction=getattr(operator, "direction", 1))
    scratch_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in scratch_root.parts:
        raise ValueError("Native scratch must be under .runtime-work")
    scratch_root.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="c135705-attempt-", dir=scratch_root))
    archives = {}
    started = False
    frames, width_history = [], []
    try:
        _write(root / "alley_geometry.json", geometry)
        (root / "road.xodr").write_bytes(map_bytes)
        operator.start(plan)
        started = True
        actors = operator.read_actor_inventory()
        if actors.get("ego_vehicle_id") != geometry.get("ego_vehicle_id") or not actors.get("ego_actual_blueprint") or not actors.get("ego_actual_dimensions_m"):
            raise ValueError("actual ego actor readback missing")
        if variant.startswith("other_vehicle") and (not actors.get("other_vehicle_id") or not actors.get("other_actual_blueprint") or not actors.get("other_actual_dimensions_m")):
            raise ValueError("actual controlled other vehicle readback missing")
        _write(root / "actor_inventory.json", actors)
        archives = {name: zipfile.ZipFile(root / (name + ".zip"), "w", zipfile.ZIP_STORED)
                    for name in sorted(CAMERAS)}
        for index in range(FRAMES):
            tick = operator.tick()
            frame, time_s = tick.get("frame"), tick.get("time_s")
            if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
                raise ValueError("original Native frame identity missing")
            if frames and (frame != frames[-1]["frame"] + 1 or abs(time_s - frames[-1]["time_s"] - 0.05) > 0.001):
                raise ValueError("original Native frame gap or cadence drift")
            if after_tick is not None:
                after_tick(frame, time_s)
            row = operator.read_width_history(frame)
            if row.get("frame") != frame or row.get("time_s") != time_s or not row.get("source"):
                raise ValueError("original body width source/frame mismatch")
            if row.get("ego_vehicle_id") != actors["ego_vehicle_id"]:
                raise ValueError("original ego body identity mismatch")
            if variant.startswith("other_vehicle") and row.get("other_vehicle_id") != actors["other_vehicle_id"]:
                raise ValueError("original controlled other body identity mismatch")
            cameras = operator.read_cameras(frame)
            if not isinstance(cameras, dict) or set(cameras) != CAMERAS:
                raise ValueError("four original camera sources missing")
            for name in sorted(CAMERAS):
                packet = cameras[name]
                raw = packet.get("png")
                if packet.get("frame") != frame or packet.get("time_s") != time_s or not isinstance(raw, bytes) or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("original camera frame missing: " + name)
                archives[name].writestr(f"{index:04d}-{frame}.png", raw)
            frames.append({"frame": frame, "time_s": time_s, "video_frame": index})
            width_history.append(row)
        if hashlib.sha256(operator.get_opendrive_bytes()).hexdigest() != geometry["map_sha256"]:
            raise ValueError("original map changed during capture")
        operator.capture_complete = True
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    finally:
        for archive in archives.values():
            archive.close()
        try:
            if started:
                operator.brake()
        finally:
            try:
                operator.cleanup()
            except BaseException:
                shutil.rmtree(root, ignore_errors=True)
                raise
    try:
        sources = {"frame_map": {"frames":frames},
                   "alley_geometry": geometry,
                   "width_history": {"case_id":case_id, "source_kind":"original_native", "samples":width_history}}
        inventory = {"case_id":case_id, "source_kind":"original_native", "frame_count":FRAMES, "sources":{},
                     "diagnostic_fixture":not bool(getattr(operator,"native_attested",False)),
                     "map_sha256":geometry["map_sha256"], "media":{}}
        for name, value in sources.items():
            filename = name + ".json"
            inventory["sources"][name] = {"path":filename,"sha256":_write(root / filename,value)}
        for name in sorted(CAMERAS):
            filename = name + ".zip"
            inventory["media"][name] = {"path":filename,"sha256":hashlib.sha256((root / filename).read_bytes()).hexdigest()}
        if not inventory["diagnostic_fixture"]:
            inventory["physical_completion"] = False
        _write(root / "inventory.json", inventory)
        measurement = measure_saved(root, case_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(root, destination)
        return {"case_id":case_id,"frame_count":FRAMES,
                "minimum_available_continuous_width_ft":measurement["minimum_available_continuous_width_ft"],
                "diagnostic_fixture":inventory["diagnostic_fixture"],
                "free_movement_judgment":"unresolved"}
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
