"""Seal one original 20 Hz crosswalk attempt from a supplied Native adapter.

The adapter owns CARLA world setup, control and cleanup. This writer retains
original world frame/time alongside the 0-based episode axis used by saved
measurement. A CPU adapter can test joins but cannot prove Native provenance.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image

import crosswalk

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
              "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _require(value, message):
    if not value:
        raise ValueError(message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8")


def capture(adapter, scene_path, site_path, exception_path, output,
            *, frame_count=600, dimensions=None):
    scene_path, site_path = Path(scene_path), Path(site_path)
    exception_path, output = Path(exception_path), Path(output)
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    site_bytes = site_path.read_bytes()
    exception_bytes = exception_path.read_bytes()
    site = json.loads(site_bytes)
    exception = json.loads(exception_bytes)
    _require(scene["rate_hz"] == 20 and scene["duration_s"] == 30 and frame_count == 600,
             "exact 600-frame 20 Hz scene required")
    _require(tuple(scene["camera_contract"]) == CAMERAS, "wrong four-camera contract")
    crosswalk.bind_site(site, site["map_name"], scene["turn_direction"])
    _require(exception.get("case_id") == scene["case_id"] and exception.get("source_refs")
             and exception.get("status") in ("none_identified", "possible", "applies"),
             "independent exception review source missing")
    attestation = adapter.source_attestation()
    _require(isinstance(attestation, dict) and attestation.get("native_origin") is True
             and attestation.get("map_name") == site["map_name"]
             and attestation.get("site_sha256") == _sha(site_bytes)
             and attestation.get("source_ref"), "Native source attestation mismatch")
    _require(not output.exists() or not any(output.iterdir()),
             "Native output attempt must be empty")
    output.mkdir(parents=True, exist_ok=True)
    frame_dir = output / "original-frames"
    frame_dir.mkdir()
    dims = DIMENSIONS if dimensions is None else dimensions
    _require(set(dims) == set(CAMERAS), "four camera dimensions required")
    ego_rows, pedestrian_rows, map_rows, camera_rows = [], [], [], []
    previous_native_frame = None
    previous_native_time = None
    start_native_time = None
    actor_ids = None
    for index in range(frame_count):
        original = adapter.tick()
        _require(isinstance(original, dict), "original Native tick packet missing")
        frame, native_time = original.get("native_frame"), original.get("native_elapsed_s")
        _require(type(frame) is int and isinstance(native_time, (float, int))
                 and math.isfinite(native_time), "original Native frame/time missing")
        if previous_native_frame is not None:
            _require(frame == previous_native_frame + 1, "original Native frame gap")
            _require(abs(native_time - previous_native_time - .05) <= .001,
                     "original Native 20 Hz time gap")
        previous_native_frame, previous_native_time = frame, native_time
        if start_native_time is None:
            start_native_time = native_time
        _require(abs(native_time - start_native_time - index / 20) <= .001,
                 "episode time diverged from original Native clock")
        driver, person, images = original.get("ego"), original.get("pedestrian"), original.get("cameras")
        _require(isinstance(driver, dict) and isinstance(person, dict),
                 "two original participant samples required")
        ids = (driver.get("actor_id"), person.get("actor_id"))
        _require(all(type(value) is int for value in ids) and ids[0] != ids[1],
                 "original participant identity missing")
        if actor_ids is None:
            actor_ids = ids
        _require(ids == actor_ids, "original participant identity drift")
        _require(driver.get("classification") == "motor_vehicle_driver"
                 and person.get("classification") == "pedestrian",
                 "original participant classification missing")
        for row in (driver, person):
            point = row.get("body_center_xy_m")
            _require(isinstance(point, list) and len(point) == 2
                     and all(isinstance(v, (int, float)) and math.isfinite(v) for v in point),
                     "original participant body center missing")
        _require(isinstance(images, dict) and set(images) == set(CAMERAS),
                 "four original camera images required")
        refs = {}
        for name in CAMERAS:
            data = images[name]
            _require(isinstance(data, bytes) and data, "original camera bytes missing")
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                _require(image.format == "PNG" and image.size == tuple(dims[name])
                         and image.mode in ("RGB", "RGBA"), "camera PNG profile mismatch")
            path = frame_dir / f"{name}-{index:06d}.png"
            path.write_bytes(data)
            refs[name] = {"path": str(path.relative_to(output)), "sha256": _sha(data)}
        row_base = {"frame": index, "elapsed_s": index / 20,
                    "native_frame": frame, "native_elapsed_s": native_time}
        ego_rows.append({**driver, **row_base})
        pedestrian_rows.append({**person, **row_base})
        map_rows.append(row_base)
        camera_rows.append({**row_base, "views": refs})
    files = {}
    for name, value in (("site", site), ("ego", ego_rows),
                        ("pedestrian", pedestrian_rows),
                        ("exception_review", exception),
                        ("frame_map", map_rows), ("camera_manifest", camera_rows)):
        path = output / (name + ".json")
        if name == "site":
            path.write_bytes(site_bytes)
        elif name == "exception_review":
            path.write_bytes(exception_bytes)
        else:
            _write_json(path, value)
        files[name] = {"path": path.name, "sha256": _sha(path.read_bytes()),
                       "source": "native_original"}
    index = {"format": "c111610-native-source-index-v1", "case_id": scene["case_id"],
             "scene_sha256": _sha(scene_path.read_bytes()), "map_name": site["map_name"],
             "native_source_attestation": attestation, "files": files,
             "physical_acceptance_claimed": False, "legal_judgment": None}
    _write_json(output / "source-index.json", index)
    return index
