"""Acquire original Native business-alley activity and four camera streams.

The injected operator supplies real tick, actor and camera readback. A source-
reviewed construction target is never copied into the activity observation.
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

from alley_construction import ASSIGNMENT, VARIANTS, build_plan
from alley_activity import measure_original_activity

CAMERAS = frozenset(("overview", "approach", "reference_corner", "driver_reference"))
FRAME_COUNT = 900


def _write_json(path, value):
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _scratch():
    raw = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not raw:
        raise ValueError("Native scratch output root missing")
    root = Path(raw).resolve()
    if ".runtime-work" not in root.parts:
        raise ValueError("Native scratch must be under .runtime-work")
    root.mkdir(parents=True, exist_ok=True)
    return root


def capture(operator, case_id, destination, *, direction=1, after_tick=None):
    """Capture one immutable original attempt after reading a reviewed site packet."""
    if not case_id.startswith(ASSIGNMENT + "__") or case_id.removeprefix(ASSIGNMENT + "__") not in VARIANTS:
        raise ValueError("unknown exact business-alley case")
    destination = Path(destination)
    if destination.exists():
        raise ValueError("refusing to replace original attempt")
    site = operator.get_map_packet(case_id)
    if site.get("case_id") != case_id or site.get("source_kind") != "reviewed_original_native_site":
        raise ValueError("reviewed original site packet missing")
    plan = build_plan(site, case_id, direction=direction)
    map_bytes = operator.get_opendrive_bytes()
    if not isinstance(map_bytes, bytes) or hashlib.sha256(map_bytes).hexdigest() != site["reviewed_sources"]["map"]["sha256"]:
        raise ValueError("actual Native map differs from reviewed map")
    if after_tick is not None and not callable(after_tick):
        raise ValueError("same-tick graph callback invalid")
    root = Path(tempfile.mkdtemp(prefix="c378707-original-", dir=_scratch()))
    archives = {}
    started = False
    frames = []
    rows = []
    first_time = None
    try:
        site_sha = _write_json(root / "site.json", site)
        plan_sha = _write_json(root / "plan.json", plan)
        (root / "road.xodr").write_bytes(map_bytes)
        operator.start(plan)
        started = True
        actors = operator.read_actor_inventory()
        for key in ("ego_vehicle_id", "ego_actual_blueprint", "ego_actual_dimensions_m",
                    "passenger_actor_id", "goods_actor_id", "driver_actor_id"):
            if not actors.get(key):
                raise ValueError("original actor readback missing: " + key)
        actors_sha = _write_json(root / "actors.json", actors)
        archives = {name: zipfile.ZipFile(root / (name + ".zip"), "w", zipfile.ZIP_STORED)
                    for name in sorted(CAMERAS)}
        for index in range(FRAME_COUNT):
            tick = operator.tick()
            native_frame, native_time = tick.get("frame"), tick.get("time_s")
            if (type(native_frame) is not int or type(native_time) not in (int, float) or
                    not math.isfinite(native_time)):
                raise ValueError("original Native tick missing")
            if index == 0:
                first_time = native_time
            elif (native_frame != frames[-1]["native_frame"] + 1 or
                  abs(native_time - frames[-1]["native_time_s"] - 0.05) > 0.001):
                raise ValueError("original Native frame gap or cadence drift")
            if after_tick is not None:
                after_tick(native_frame, native_time)
            activity = operator.read_activity(native_frame)
            if (activity.get("frame") != native_frame or
                    activity.get("time_s") != native_time or
                    activity.get("source_kind") != "original_native" or
                    activity.get("case_id") != case_id or
                    activity.get("ego_vehicle_id") != actors["ego_vehicle_id"] or
                    activity.get("passenger_actor_id") != actors["passenger_actor_id"] or
                    activity.get("goods_actor_id") != actors["goods_actor_id"] or
                    activity.get("driver_actor_id") != actors["driver_actor_id"]):
                raise ValueError("original activity actor or tick identity mismatch")
            camera_packets = operator.read_cameras(native_frame)
            if not isinstance(camera_packets, dict) or set(camera_packets) != CAMERAS:
                raise ValueError("four original camera streams missing")
            for name in sorted(CAMERAS):
                packet = camera_packets[name]
                png = packet.get("png")
                if (packet.get("frame") != native_frame or packet.get("time_s") != native_time or
                        not isinstance(png, bytes) or not png.startswith(b"\x89PNG\r\n\x1a\n")):
                    raise ValueError("original camera frame missing: " + name)
                archives[name].writestr(f"{index:04d}-{native_frame}.png", png)
            row = dict(activity)
            row["native_frame"] = native_frame
            row["native_time_s"] = native_time
            row["frame"] = index
            row["time_s"] = index / 20
            frames.append({"frame": index, "time_s": index / 20,
                           "native_frame": native_frame, "native_time_s": native_time})
            rows.append(row)
        if hashlib.sha256(operator.get_opendrive_bytes()).hexdigest() != site["reviewed_sources"]["map"]["sha256"]:
            raise ValueError("Native map changed during capture")
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    finally:
        for archive in archives.values():
            archive.close()
        try:
            graph = getattr(operator, "pipeline_capture", None)
            if graph is not None:
                graph.close(confirmed=len(frames) == FRAME_COUNT)
            if started:
                operator.brake()
        finally:
            if started:
                operator.cleanup()
                operator.capture_cleanup_complete = True
    try:
        activity_bytes = ("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":"))
                                    for row in rows) + "\n").encode()
        (root / "activity.jsonl").write_bytes(activity_bytes)
        seal_sha = _write_json(root / "activity-seal.json", {
            "format": "original-alley-activity-seal", "case_id": case_id,
            "frame_count": FRAME_COUNT, "rate_hz": 20,
            "history_sha256": hashlib.sha256(activity_bytes).hexdigest(),
        })
        frame_map_sha = _write_json(root / "frame-map.json", {"case_id": case_id, "frames": frames})
        measured = measure_original_activity(root / "activity.jsonl", root / "activity-seal.json", case_id)
        measurement_sha = _write_json(root / "activity-measurement.json", measured)
        media = {name: {"path": name + ".zip",
                        "sha256": hashlib.sha256((root / (name + ".zip")).read_bytes()).hexdigest()}
                 for name in sorted(CAMERAS)}
        _write_json(root / "inventory.json", {
            "case_id": case_id, "source_kind": "original_native",
            "frame_count": FRAME_COUNT, "rate_hz": 20, "media": media,
            "activity_sha256": hashlib.sha256(activity_bytes).hexdigest(),
            "map_sha256": site["reviewed_sources"]["map"]["sha256"],
            "source_sha256": {"site.json": site_sha, "plan.json": plan_sha,
                              "actors.json": actors_sha, "activity-seal.json": seal_sha,
                              "frame-map.json": frame_map_sha,
                              "activity-measurement.json": measurement_sha},
            "diagnostic_fixture": not bool(getattr(operator, "native_attested", False)),
            "physical_completion": False,
        })
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(root, destination)
        return measured
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
