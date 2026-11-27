"""Synchronized original driveway capture with source inventory and cleanup.

The supplied operator owns a CARLA client, actors and four sensors. A diagnostic
operator is explicitly marked synthetic and cannot be promoted as Native proof.
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

from driveway_construction import construct

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _write(path, value):
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def capture(operator, case, destination, *, diagnostic=False, after_tick=None):
    """Acquire one 20 Hz episode, retaining no partial successful attempt.

    Required operator protocol: geometry_packet(case_id), opendrive_bytes(),
    start(plan), tick(), activity(frame), cameras(frame), brake(), cleanup().
    A real session must set native_attested and verify_restoration on cleanup.
    """
    destination = Path(destination)
    if destination.exists():
        raise ValueError("original attempt destination already exists")
    if after_tick is not None and not callable(after_tick):
        raise ValueError("same-tick Core graph capture callback required")
    if not diagnostic and not getattr(operator, "native_attested", False):
        raise ValueError("original Native operator attestation missing")
    geometry = operator.geometry_packet(case["case_id"])
    if diagnostic:
        if geometry.get("source_kind") != "synthetic_fixture":
            raise ValueError("diagnostic source provenance differs")
        surveyed = dict(geometry, source_kind="original_native_geometry")
    else:
        surveyed = geometry
    plan = construct(surveyed, case)
    map_bytes = operator.opendrive_bytes()
    if not isinstance(map_bytes, bytes) or hashlib.sha256(map_bytes).hexdigest() != geometry["map_sha256"]:
        raise ValueError("reviewed OpenDRIVE bytes differ from original map")
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="driveway-original-", dir=destination.parent))
    archives = {}
    begun = False
    frames, activities = [], []
    count = 9 if diagnostic else 900
    try:
        _write(scratch / "driveway_geometry.json", geometry)
        (scratch / "road.xodr").write_bytes(map_bytes)
        operator.start(plan)
        begun = True
        archives = {name: zipfile.ZipFile(scratch / (name + ".zip"), "w", zipfile.ZIP_STORED)
                    for name in VIEWS}
        for index in range(count):
            row = operator.tick()
            frame, time_s = row.get("frame"), row.get("time_s")
            if (type(frame) is not int or type(time_s) not in (int, float) or
                    not math.isfinite(time_s)):
                raise ValueError("original frame/time identity missing")
            if frames and (frame != frames[-1]["frame"] + 1 or
                           abs(time_s - frames[-1]["time_s"] - .05) > .001):
                raise ValueError("original Native cadence drift")
            if after_tick is not None:
                after_tick(frame, time_s)
            activity = operator.activity(frame)
            if activity.get("frame") != frame or activity.get("time_s") != time_s:
                raise ValueError("original activity/frame join differs")
            if activity.get("ego", {}).get("actor_id") != geometry["ego_vehicle_id"]:
                raise ValueError("original ego actor identity differs")
            cameras = operator.cameras(frame)
            if not isinstance(cameras, dict) or set(cameras) != set(VIEWS):
                raise ValueError("four original camera views missing")
            for name in VIEWS:
                image = cameras[name]
                raw = image.get("png")
                if (image.get("frame") != frame or image.get("time_s") != time_s or
                        not isinstance(raw, bytes) or not raw.startswith(b"\x89PNG\r\n\x1a\n")):
                    raise ValueError("original camera frame missing: " + name)
                archives[name].writestr(f"{index:04d}-{frame}.png", raw)
            frames.append({"video_frame": index, "frame": frame, "time_s": time_s})
            activities.append(activity)
        if hashlib.sha256(operator.opendrive_bytes()).hexdigest() != geometry["map_sha256"]:
            raise ValueError("original Native map changed during attempt")
        operator.capture_complete = True
    except BaseException:
        shutil.rmtree(scratch, ignore_errors=True)
        raise
    finally:
        for archive in archives.values():
            archive.close()
        try:
            if begun:
                operator.brake()
        finally:
            operator.cleanup()
    if not diagnostic and not getattr(operator, "restored", False):
        shutil.rmtree(scratch, ignore_errors=True)
        raise ValueError("original world restoration readback unverified")
    try:
        kind = "synthetic_fixture" if diagnostic else "original_native"
        sources = {
            "frame_map": {"frames": frames},
            "driveway_geometry": geometry,
            "activity": {"case_id": case["case_id"], "source_kind": kind, "samples": activities},
        }
        inventory = {"case_id": case["case_id"], "source_kind": kind,
                     "diagnostic_fixture": diagnostic, "sources": {}, "media": {},
                     "map_sha256": geometry["map_sha256"],
                     "physical_acceptance_claimed": False}
        for name, value in sources.items():
            inventory["sources"][name] = {"path": name + ".json",
                                           "sha256": _write(scratch / (name + ".json"), value)}
        for name in VIEWS:
            path = scratch / (name + ".zip")
            inventory["media"][name] = {"path": path.name,
                                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        _write(scratch / "inventory.json", inventory)
        os.replace(scratch, destination)
        return inventory
    except BaseException:
        shutil.rmtree(scratch, ignore_errors=True)
        raise
