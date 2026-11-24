"""Project original Native actor bodies into the surveyed opposing-road frame.

The supplied adapter owns world ticks, controls and actor cleanup. This module
seals observed motion only; requested routes never substitute for body readback.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image

from opposing_pass import _number, construct, load_sealed, measure, world_routes

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CAMERA_DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
                     "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _project(vertices, origin, forward):
    if not isinstance(vertices, list) or len(vertices) != 8:
        raise ValueError("eight original body vertices required")
    left = (-forward[1], forward[0])
    stations, laterals = [], []
    for vertex in vertices:
        if not isinstance(vertex, (list, tuple)) or len(vertex) != 3:
            raise ValueError("original world vertex missing")
        x, y, z = map(_number, vertex)
        stations.append((x-origin[0])*forward[0] + (y-origin[1])*forward[1])
        laterals.append((x-origin[0])*left[0] + (y-origin[1])*left[1])
    return [min(stations), max(stations)], [min(laterals), max(laterals)]


def _paved(packet, ego_station, other_station):
    rows = packet["cross_sections"]
    midpoint = (ego_station + other_station) / 2
    row = min(rows, key=lambda item: abs(_number(item["s_m"]) - midpoint))
    if abs(_number(row["s_m"]) - midpoint) > 5:
        raise ValueError("original bodies outside surveyed cross sections")
    return list(map(_number, row["paved_y_bounds_m"]))


def capture(adapter, map_path, expected_map_sha256, variant, output,
            *, frames=900, diagnostic_fixture=False, media_output=None,
            camera_dimensions=None):
    """Write a once-only source-hashed trace for the exact variant."""
    if frames != 900 and not diagnostic_fixture:
        raise ValueError("production capture requires 900 original frames")
    if type(frames) is not int or frames < 2:
        raise ValueError("original frame count invalid")
    packet = load_sealed(map_path, expected_map_sha256)
    construct(packet, variant)
    world_routes(packet, variant)
    attestation = adapter.source_attestation()
    if not isinstance(attestation, dict) or not attestation.get("native_origin") \
            or attestation.get("map_sha256") != expected_map_sha256 \
            or not attestation.get("source_ref"):
        raise ValueError("original Native map attestation mismatch")
    frame = packet["native_road_frame"]
    origin = list(map(_number, frame["origin_xyz_m"]))
    forward = list(map(_number, frame["forward_xy"]))
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    media_root = Path(media_output) if media_output is not None else None
    dims = CAMERA_DIMENSIONS if camera_dimensions is None else camera_dimensions
    if media_root is not None:
        if media_root.exists():
            raise FileExistsError(media_root)
        if set(dims) != set(CAMERAS):
            raise ValueError("four original camera dimensions required")
        media_root.mkdir(parents=True)
    rows, actor_ids = [], None
    camera_rows = []
    first_time = previous_time = previous_frame = None
    for index in range(frames):
        sample = adapter.tick()
        if not isinstance(sample, dict):
            raise ValueError("original Native tick packet absent")
        native_frame = sample.get("native_frame")
        native_time = sample.get("native_elapsed_s")
        if type(native_frame) is not int or not isinstance(native_time, (int, float)) \
                or not math.isfinite(native_time):
            raise ValueError("original Native frame/time absent")
        if previous_frame is not None and (native_frame != previous_frame + 1 or
                abs(native_time - previous_time - .05) > .001):
            raise ValueError("original Native 20 Hz frame/time gap")
        if first_time is None:
            first_time = native_time
        if abs(native_time - first_time - index/20) > .001:
            raise ValueError("episode time diverged from original Native clock")
        previous_frame, previous_time = native_frame, native_time
        if media_root is not None:
            images = sample.get("cameras")
            if not isinstance(images, dict) or set(images) != set(CAMERAS):
                raise ValueError("four original cameras required per Native tick")
            view_refs = {}
            for name in CAMERAS:
                data = images[name]
                if not isinstance(data, bytes) or not data:
                    raise ValueError("original camera bytes missing")
                with Image.open(io.BytesIO(data)) as image:
                    image.load()
                    if (image.format != "PNG" or image.size != tuple(dims[name]) or
                            image.mode not in ("RGB", "RGBA")):
                        raise ValueError("original camera profile mismatch")
                path = media_root / f"{name}-{index:06d}.png"
                path.write_bytes(data)
                view_refs[name] = {"path": path.name,
                                   "sha256": hashlib.sha256(data).hexdigest()}
            camera_rows.append({"frame": index, "time_s": index/20,
                                "native_frame": native_frame,
                                "native_elapsed_s": native_time,
                                "views": view_refs})
        ego, other = sample.get("ego"), sample.get("other")
        if not isinstance(ego, dict) or not isinstance(other, dict):
            raise ValueError("two original actor samples required")
        ids = (ego.get("actor_id"), other.get("actor_id"))
        if not all(isinstance(v, (int, str)) and v for v in ids) or ids[0] == ids[1]:
            raise ValueError("distinct original actor IDs required")
        if actor_ids is None:
            actor_ids = ids
        if ids != actor_ids:
            raise ValueError("original actor identity drift")
        ego_s, ego_y = _project(ego.get("vertices_world_xyz_m"), origin, forward)
        other_s, other_y = _project(other.get("vertices_world_xyz_m"), origin, forward)
        ego_velocity = ego.get("velocity_world_xyz_mps")
        other_velocity = other.get("velocity_world_xyz_mps")
        if not isinstance(ego_velocity, list) or not isinstance(other_velocity, list) \
                or len(ego_velocity) != 3 or len(other_velocity) != 3:
            raise ValueError("original world velocity missing")
        ev = list(map(_number, ego_velocity))
        ov = list(map(_number, other_velocity))
        lo, hi = _paved(packet, sum(ego_s)/2, sum(other_s)/2)
        rows.append({"frame": index, "time_s": index/20,
                     "native_frame": native_frame, "native_elapsed_s": native_time,
                     "ego_id": ids[0], "other_id": ids[1],
                     "ego_speed_s_mps": ev[0]*forward[0]+ev[1]*forward[1],
                     "other_speed_s_mps": ov[0]*forward[0]+ov[1]*forward[1],
                     "paved_y_bounds_m": [lo, hi],
                     "ego_body_s_bounds_m": ego_s, "other_body_s_bounds_m": other_s,
                     "ego_body_y_bounds_m": ego_y, "other_body_y_bounds_m": other_y})
    trace = {"source_kind": "original_native_actor_history",
             "map_source_kind": packet["source_kind"],
             "map_sha256": expected_map_sha256, "variant": variant,
             "public_highway": packet["public_highway"],
             "encounter_on_undivided_approach": packet["encounter_on_undivided_approach"],
             "traffic_line_capacity_each_direction": packet["traffic_line_capacity_each_direction"],
             "capacity_source": packet["capacity_source"],
             "paved_boundary_source": packet["paved_boundary_source"],
             "actor_ids": list(actor_ids), "samples": rows,
             "native_source_attestation": attestation,
             "diagnostic_fixture": diagnostic_fixture,
             "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}
    measure(trace)
    output.write_text(json.dumps(trace, sort_keys=True, separators=(",", ":")) + "\n",
                      encoding="utf-8")
    receipt = {"path": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "frame_count": frames, "diagnostic_fixture": diagnostic_fixture}
    if media_root is not None:
        manifest = media_root / "camera-manifest.json"
        manifest.write_text(json.dumps(camera_rows, sort_keys=True, separators=(",", ":")) + "\n",
                            encoding="utf-8")
        receipt["camera_manifest"] = {"path": str(manifest),
                                      "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                                      "view_frames": frames * len(CAMERAS)}
    return receipt


def audit_media(trace_path, expected_trace_sha256, media_root, expected_manifest_sha256,
                *, dimensions=None):
    """Reopen and decode each retained camera against the original actor clock."""
    trace = load_sealed(trace_path, expected_trace_sha256)
    rows = trace.get("samples")
    if not isinstance(rows, list) or not rows:
        raise ValueError("original actor samples missing")
    root = Path(media_root)
    manifest_path = root / "camera-manifest.json"
    camera_rows = load_sealed(manifest_path, expected_manifest_sha256)
    if not isinstance(camera_rows, list) or len(camera_rows) != len(rows):
        raise ValueError("camera/actor frame count mismatch")
    dims = CAMERA_DIMENSIONS if dimensions is None else dimensions
    if set(dims) != set(CAMERAS):
        raise ValueError("four original camera dimensions required")
    for index, (actor, camera) in enumerate(zip(rows, camera_rows)):
        if any(camera.get(key) != actor.get(key) for key in
               ("frame", "time_s", "native_frame", "native_elapsed_s")):
            raise ValueError(f"camera/actor original clock mismatch at {index}")
        views = camera.get("views")
        if not isinstance(views, dict) or set(views) != set(CAMERAS):
            raise ValueError("four original camera views required")
        for name in CAMERAS:
            entry = views[name]
            expected_name = f"{name}-{index:06d}.png"
            if entry.get("path") != expected_name:
                raise ValueError("original camera path mismatch")
            data = (root / expected_name).read_bytes()
            if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
                raise ValueError("original camera bytes changed")
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                if (image.format != "PNG" or image.size != tuple(dims[name]) or
                        image.mode not in ("RGB", "RGBA")):
                    raise ValueError("original camera decode/profile mismatch")
    return {"trace_sha256": expected_trace_sha256,
            "camera_manifest_sha256": expected_manifest_sha256,
            "joined_frames": len(rows), "decoded_view_frames": len(rows)*len(CAMERAS),
            "diagnostic_fixture": trace.get("diagnostic_fixture") is True,
            "physical_acceptance": False, "legal_judgment": "unresolved"}
