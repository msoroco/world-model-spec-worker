"""Capture an original private-way episode with complete highway actor sources.

The injected operator supplies actual CARLA actor and camera readback. This
module owns one source-sealed attempt and always releases spawned resources.
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

from private_way_construction import ASSIGNMENT, CASES, build_plan
from private_way_site import load_site, REQUIRED_SOURCES
from private_way_motion import measure


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
FRAME_COUNT = 900


def _write_json(path, value):
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _scratch():
    raw = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not raw:
        raise ValueError("Native scratch output root missing")
    root = Path(raw).resolve()
    if ".runtime-work" not in root.parts:
        raise ValueError("Native scratch must be under .runtime-work")
    root.mkdir(parents=True, exist_ok=True)
    return root


def capture(operator, case_id, destination, *, spawn_offset_m=0.0,
            after_tick=None, diagnostic_frames=None):
    """Capture one exact attempt without replacing any prior original output."""
    if not case_id.startswith(ASSIGNMENT + "__") or \
            case_id.removeprefix(ASSIGNMENT + "__") not in CASES:
        raise ValueError("unknown exact private-way case")
    if after_tick is not None and not callable(after_tick):
        raise ValueError("same-tick graph callback invalid")
    frames_expected = FRAME_COUNT if diagnostic_frames is None else diagnostic_frames
    if frames_expected not in (9, FRAME_COUNT) or \
            (frames_expected == 9 and getattr(operator, "native_attested", False)):
        raise ValueError("diagnostic frame count cannot represent attested Native capture")
    destination = Path(destination)
    if destination.exists():
        raise ValueError("refusing to replace original private-way attempt")
    packet = Path(operator.get_site_packet(case_id)).resolve()
    site = load_site(packet, case_id)
    plan = build_plan(site, case_id, spawn_offset_m=spawn_offset_m)
    map_bytes = operator.get_opendrive_bytes()
    if not isinstance(map_bytes, bytes) or \
            hashlib.sha256(map_bytes).hexdigest() != site["sources"]["native_opendrive_map"]["sha256"]:
        raise ValueError("actual Native map differs from reviewed map")
    root = Path(tempfile.mkdtemp(prefix="c228096-original-", dir=_scratch()))
    archives = {}
    rows = []
    frame_map = []
    first_native = None
    first_time = None
    started = False
    completed = False
    try:
        sealed_site = json.loads(json.dumps(site))
        for name in REQUIRED_SOURCES:
            entry = site["sources"][name]
            source = (packet.parent / entry["path"]).resolve()
            target = root / "site-sources" / (name + ".source")
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(source, target)
            if _sha(target) != entry["sha256"]:
                raise ValueError("reviewed source changed during acquisition: " + name)
            sealed_site["sources"][name]["path"] = str(target.relative_to(root))
        _write_json(root / "site.json", sealed_site)
        _write_json(root / "plan.json", plan)
        (root / "road.xodr").write_bytes(map_bytes)
        started = True
        operator.start(plan)
        inventory = operator.read_actor_inventory()
        expected_sides = set(CASES[case_id.removeprefix(ASSIGNMENT + "__")][1])
        if not isinstance(inventory, dict) or not inventory.get("ego_vehicle_id") or \
                set(inventory.get("highway_vehicles", {})) != expected_sides or \
                any(not value for value in inventory["highway_vehicles"].values()):
            raise ValueError("original private-way actor inventory incomplete")
        _write_json(root / "actors.json", inventory)
        archives = {name: zipfile.ZipFile(root / (name + ".zip"), "w", zipfile.ZIP_STORED)
                    for name in CAMERAS}
        for index in range(frames_expected):
            tick = operator.tick()
            native_frame = tick.get("frame")
            native_time = tick.get("time_s")
            if type(native_frame) is not int or type(native_time) not in (int, float) or \
                    not math.isfinite(native_time):
                raise ValueError("original Native tick missing")
            if index == 0:
                first_native, first_time = native_frame, native_time
            elif native_frame != first_native + index or \
                    abs(native_time - first_time - index / 20) > .005:
                raise ValueError("original Native frame or 20 Hz cadence gap")
            if after_tick is not None:
                after_tick(native_frame, native_time)
            state = operator.read_motion(native_frame)
            if not isinstance(state, dict) or state.get("native_frame") != native_frame or \
                    state.get("case_id") != case_id or state.get("source_kind") != "original_native" or \
                    state.get("ego_vehicle_id") != inventory["ego_vehicle_id"]:
                raise ValueError("original Native motion identity differs")
            actors = state.get("highway_vehicles")
            if not isinstance(actors, list) or \
                    {row.get("side") for row in actors} != expected_sides or \
                    any(row.get("actor_id") != inventory["highway_vehicles"].get(row.get("side"))
                        for row in actors):
                raise ValueError("original highway actor readback incomplete")
            cameras = operator.read_cameras(native_frame)
            if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
                raise ValueError("four original camera sources missing")
            for name in CAMERAS:
                camera = cameras[name]
                png = camera.get("png")
                if camera.get("frame") != native_frame or \
                        camera.get("time_s") != native_time or \
                        not isinstance(png, bytes) or not png.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("original camera frame missing: " + name)
                archives[name].writestr(f"{index:04d}-{native_frame}.png", png)
            row = dict(state)
            row["frame"] = index
            row["time_s"] = native_time
            rows.append(row)
            frame_map.append({"frame": index, "native_frame": native_frame,
                              "native_time_s": native_time})
        if hashlib.sha256(operator.get_opendrive_bytes()).hexdigest() != \
                site["sources"]["native_opendrive_map"]["sha256"]:
            raise ValueError("Native road map changed during capture")
        completed = True
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    finally:
        for archive in archives.values():
            archive.close()
        if started:
            try:
                operator.brake()
            finally:
                operator.cleanup()
                operator.capture_cleanup_complete = True
    try:
        if not completed:
            raise ValueError("original private-way capture incomplete")
        history = root / "motion.jsonl"
        history.write_text("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":"))
                                     for row in rows) + "\n")
        _write_json(root / "motion-seal.json", {
            "format": "worker-private-way-motion-seal", "case_id": case_id,
            "frame_count": frames_expected,
            "diagnostic_fixture": frames_expected == 9,
            "motion_sha256": _sha(history), "site_sha256": _sha(root / "site.json"),
        })
        _write_json(root / "frame-map.json", {"case_id": case_id,
                                              "frames": frame_map})
        observed = measure(root, case_id)
        _write_json(root / "motion-measurement.json", observed)
        media = operator.encode_media(root, CAMERAS, frame_map)
        if not isinstance(media, dict) or set(media) != set(CAMERAS) | {"raw"} or \
                any(not (root / (name + ".mkv")).is_file() or
                    (root / (name + ".mkv")).stat().st_size == 0
                    for name in media):
            raise ValueError("original four-view encoded media incomplete")
        _write_json(root / "inventory.json", {
            "case_id": case_id,
            "source_kind": "original_native" if frames_expected == FRAME_COUNT else "synthetic_fixture",
            "frame_count": frames_expected,
            "camera_archives": {name: {"path": name + ".zip",
                                       "sha256": _sha(root / (name + ".zip"))}
                                for name in CAMERAS},
            "media": {name: {"path": name + ".mkv",
                             "sha256": _sha(root / (name + ".mkv"))}
                      for name in sorted(media)},
            "motion_sha256": _sha(history),
            "frame_map_sha256": _sha(root / "frame-map.json"),
            "physical_acceptance_claimed": False,
        })
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(root, destination)
        return observed
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
