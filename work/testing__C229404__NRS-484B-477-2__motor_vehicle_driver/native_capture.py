"""Capture original parking evidence through an injected Native adapter.

The adapter owns CARLA setup, actors and sensors. This module seals the map and
access provenance before motion, records synchronized source packets, and never
infers that geometric overlap resolves statutory blocking.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from access_measurement import ASSIGNMENT, measure
from alley_construction import build_plan

CAMERAS = frozenset(("overview", "approach", "reference_corner", "driver_reference"))
FRAMES = 900


def _write(path: Path, value: dict) -> str:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def capture(adapter, case_id: str, output: Path) -> dict:
    """Write a complete immutable attempt, or remove it on any acquisition error.

    Adapter methods: get_map_packet, start(plan), tick, read_footprint(frame),
    read_activity(frame), read_cameras(frame), brake, cleanup. The map packet
    contains source identity and qualifying-alley provenance; a static map tag
    alone is insufficient to mark a road legally qualifying.
    """
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    if not case_id.startswith(ASSIGNMENT + "__") or suffix not in {
            "driveway_clear", "driveway_overlap", "entrance_clear", "entrance_overlap"}:
        raise ValueError("unknown exact alley access case")
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError("attempt destination exists")
    geometry = adapter.get_map_packet(case_id)
    if geometry.get("case_id") != case_id or geometry.get("source_kind") != "original_native_geometry":
        raise ValueError("original alley geometry packet missing")
    if geometry.get("access_kind") != suffix.split("_", 1)[0]:
        raise ValueError("access kind differs from exact case")
    required = ("map_sha256", "highway_source", "alley_classification_source",
                "cul_de_sac_source", "property_abutting_source", "property_id",
                "driveway_ownership_source", "vehicular_use_source", "ego_vehicle_id",
                "access_corridor_polygon_m")
    if any(not geometry.get(key) for key in required):
        raise ValueError("alley/access source provenance missing")
    if geometry.get("highway_status") is not True or geometry.get("cul_de_sac") is not False:
        raise ValueError("qualifying connected highway alley unverified")
    plan = build_plan(geometry, case_id)
    map_bytes = adapter.get_opendrive_bytes()
    if not isinstance(map_bytes, bytes) or hashlib.sha256(map_bytes).hexdigest() != geometry["map_sha256"]:
        raise ValueError("Native map bytes differ from alley packet")
    root = Path(tempfile.mkdtemp(prefix="alley-attempt-", dir=destination.parent))
    archives = {}
    started = False
    frames, footprints, activities = [], [], []
    try:
        _write(root / "alley_geometry.json", geometry)
        (root / "road.xodr").write_bytes(map_bytes)
        adapter.start(plan)
        started = True
        archives = {name: zipfile.ZipFile(root / (name + ".zip"), "w", zipfile.ZIP_STORED)
                    for name in sorted(CAMERAS)}
        for index in range(FRAMES):
            tick = adapter.tick()
            frame, time_s = tick.get("frame"), tick.get("time_s")
            if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
                raise ValueError("Native frame identity missing")
            if frames and (frame != frames[-1]["frame"] + 1 or
                           abs(time_s - frames[-1]["time_s"] - .05) > .001):
                raise ValueError("Native frame gap or cadence drift")
            footprint = adapter.read_footprint(frame)
            activity = adapter.read_activity(frame)
            for packet in (footprint, activity):
                if packet.get("frame") != frame or packet.get("time_s") != time_s:
                    raise ValueError("Native source frame/time mismatch")
            if footprint.get("vehicle_id") != geometry["ego_vehicle_id"]:
                raise ValueError("Native ego vehicle identity mismatch")
            cameras = adapter.read_cameras(frame)
            if not isinstance(cameras, dict) or set(cameras) != CAMERAS:
                raise ValueError("four original camera sources missing")
            for name in sorted(CAMERAS):
                camera = cameras[name]
                raw = camera.get("png")
                if (camera.get("frame") != frame or camera.get("time_s") != time_s or
                        not isinstance(raw, bytes) or not raw.startswith(b"\x89PNG\r\n\x1a\n")):
                    raise ValueError("original camera frame missing: " + name)
                archives[name].writestr(f"{index:04d}-{frame}.png", raw)
            frames.append({"frame": frame, "time_s": time_s, "video_frame": index})
            footprints.append(footprint)
            activities.append(activity)
        if hashlib.sha256(adapter.get_opendrive_bytes()).hexdigest() != geometry["map_sha256"]:
            raise ValueError("Native map changed during attempt")
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    finally:
        for archive in archives.values():
            archive.close()
        try:
            if started:
                adapter.brake()
        finally:
            try:
                adapter.cleanup()
            except BaseException:
                shutil.rmtree(root, ignore_errors=True)
                raise
    try:
        sources = {
            "frame_map": {"frames": frames},
            "alley_geometry": geometry,
            "vehicle_footprint": {"case_id": case_id, "source_kind": "original_native", "samples": footprints},
            "activity": {"case_id": case_id, "source_kind": "original_native", "samples": activities},
        }
        inventory = {"case_id": case_id, "source_kind": "original_native", "sources": {},
                     "diagnostic_fixture": not bool(getattr(adapter, "native_attested", False)),
                     "map_sha256": geometry["map_sha256"], "media": {}}
        for name, value in sources.items():
            filename = name + ".json"
            digest = _write(root / filename, value)
            inventory["sources"][name] = {"path": filename, "sha256": digest}
        for name in sorted(CAMERAS):
            filename = name + ".zip"
            inventory["media"][name] = {"path": filename,
                                          "sha256": hashlib.sha256((root / filename).read_bytes()).hexdigest()}
        _write(root / "inventory.json", inventory)
        measured = measure(root, inventory, case_id)
        if not inventory["diagnostic_fixture"]:
            # Native attestation confirms source origin, not statutory completion.
            inventory["physical_completion"] = False
        os.replace(root, destination)
        return {"case_id": case_id, "frame_count": FRAMES,
                "max_access_intrusion_area_m2": measured["max_access_intrusion_area_m2"],
                "diagnostic_fixture": inventory["diagnostic_fixture"],
                "legal_blocking_judgment": "unresolved"}
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
