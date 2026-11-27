"""Seal original 20 Hz center-lane route, body geometry and four RGB views.

The live runner supplies a Native frame reader. No commanded waypoint or case
label is used as evidence of actual lane occupancy or maneuver completion.
"""
from __future__ import annotations

import hashlib
import json
from math import isfinite
from pathlib import Path

from center_lane_distance_probe import measure_exact
from center_lane_site import verify_reviewed_site, _read

ASSIGNMENT = "testing__C382162__NRS-484B-223-3b__motor_vehicle_driver"
KINDS = ("short_travel", "boundary_travel", "long_travel", "onto_highway_contrast")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
CAMERA_DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
                     "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _save(root, relative, value):
    path = root / relative
    if path.exists():
        raise ValueError("original source already exists: " + relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    path.write_bytes(raw)
    return {"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}


def camera_reader(attempt_root, original_reader, dimensions=None):
    """Write lossless original BGRA callbacks as frame-identified RGB PNGs."""
    from PIL import Image

    root = Path(attempt_root).resolve()
    sizes = CAMERA_DIMENSIONS if dimensions is None else dimensions
    if set(sizes) != set(VIEWS):
        raise ValueError("four exact camera dimensions required")

    def read(index):
        row = original_reader(index)
        frame, images = row.get("original_frame"), row.get("camera_images")
        if type(frame) is not int or not isinstance(images, dict) or set(images) != set(VIEWS):
            raise ValueError("four synchronized Native RGB callbacks missing")
        sources = {}
        for view in VIEWS:
            width, height = sizes[view]
            image = images[view]
            raw = getattr(image, "raw_data", None)
            if (getattr(image, "frame", None) != frame or
                    getattr(image, "width", None) != width or
                    getattr(image, "height", None) != height or
                    not isinstance(raw, (bytes, bytearray)) or len(raw) != width * height * 4):
                raise ValueError("original RGB frame or profile mismatch: " + view)
            relative = f"camera/{view}/{frame:06d}.png"
            path = root / relative
            if path.exists():
                raise ValueError("original RGB frame would overwrite source")
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.frombytes("RGBA", (width, height), bytes(raw), "raw", "BGRA").convert("RGB").save(path)
            sources[view] = {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        copied = dict(row)
        copied.pop("camera_images")
        copied["camera_sources"] = sources
        return copied

    return read


def capture_original(attempt_root, case_id, site, live_opendrive,
                     frame_reader, *, count=900):
    root = Path(attempt_root).resolve()
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("wrong exact center-lane case")
    kind = case_id.removeprefix(ASSIGNMENT + "__")
    if kind not in KINDS or type(count) is not int or count < 3:
        raise ValueError("unknown exact case or frame count")
    topology = verify_reviewed_site(root, site, kind, live_opendrive)
    rows, mapping = [], []
    first = prior = None
    for index in range(count):
        row = frame_reader(index)
        if not isinstance(row, dict):
            raise ValueError("original Native frame readback missing")
        number = row.get("original_frame")
        if type(number) is not int or (prior is not None and number != prior + 1):
            raise ValueError("original Native frame identity discontinuity")
        if first is None:
            first = number
        prior = number
        if row.get("time_s") is None or not isfinite(float(row["time_s"])) or abs(float(row["time_s"]) - index / 20) > .005:
            raise ValueError("original Native 20 Hz time drift")
        for field in ("road_id", "lane_id", "maneuver", "driver_id", "source_ref",
                      "actor_id", "body_vertices_m", "vehicle_blueprint"):
            if not row.get(field):
                raise ValueError("original Native route or vehicle source missing: " + field)
        if not str(row["vehicle_blueprint"]).startswith("vehicle."):
            raise ValueError("original ego not a motor vehicle")
        if (len(row["body_vertices_m"]) != 8 or
                any(len(vertex) != 3 or any(not isfinite(float(value)) for value in vertex)
                    for vertex in row["body_vertices_m"])):
            raise ValueError("original motor-vehicle body geometry incomplete")
        for field in ("x", "y", "z", "heading_x", "heading_y", "speed_mps"):
            if field not in row or not isfinite(float(row[field])):
                raise ValueError("original motor-vehicle kinematics missing: " + field)
        if row["speed_mps"] < 0:
            raise ValueError("original motor-vehicle speed negative")
        cameras = row.get("camera_sources")
        if not isinstance(cameras, dict) or set(cameras) != set(VIEWS):
            raise ValueError("four original camera source bindings missing")
        for view in VIEWS:
            source = cameras[view]
            data = _read(root, source)
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("original camera source is not PNG")
        rows.append({key: value for key, value in row.items() if key != "camera_sources"})
        mapping.append({"original_frame": number, "time_s": float(row["time_s"]),
                        "camera_sources": cameras})
    for row in rows:
        raw = json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        row["source_sha256"] = hashlib.sha256(raw).hexdigest()
        row["x_m"] = row["x"]
        row["y_m"] = row["y"]
    measured = measure_exact(root, site, kind, live_opendrive, rows)
    refs = {"site": _save(root, "native/site.json", site),
            "history": _save(root, "native/history.json", rows),
            "frame_map": _save(root, "native/frame-map.json", mapping)}
    _save(root, "native/inventory.json", {
        "case_id": case_id, "source_kind": "original_native", "frame_count": count,
        "camera_views": list(VIEWS), "sources": refs,
        "physical_acceptance_claimed": False})
    return measured
