"""Lazy Native capture of parked headlamp readback and original frame joins.

The caller supplies a reviewed intersection site and synchronized camera reader.
This module does not assert emitted intensity, beam aim, or legal parking status.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from lamp_probe import CASE_MODES, command_lights
from parking_geometry import classify_footprint


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _xy(vertex):
    return [float(vertex.x), float(vertex.y)]


def capture_interval(world, vehicle, light_enum, parking_control, frame_reader,
                     reviewed_site: dict, output_dir: Path, *, case_id: str,
                     mode: str, ticks: int = 900):
    """Retain original 20 Hz state and four-camera frame map for one exact case.

    `frame_reader(frame)` returns four original sensor frame identities after
    synchronization. The site packet must contain independently reviewed map
    geometry and its source hash; diagnostic polygons are explicitly labelled.
    No source file is emitted if any Native observation fails validation.
    """
    if mode not in CASE_MODES or not case_id.endswith("__" + mode):
        raise ValueError("exact case/headlamp mode mismatch")
    if ticks < 2:
        raise ValueError("capture interval needs at least two ticks")
    if parking_control.hand_brake is not True:
        raise ValueError("parking brake command required")
    if not isinstance(reviewed_site.get("source_sha256"), str) or len(reviewed_site["source_sha256"]) != 64:
        raise ValueError("reviewed site source hash required")
    site_source = Path(reviewed_site.get("source_path", ""))
    if not site_source.is_file() or _sha(site_source) != reviewed_site["source_sha256"]:
        raise ValueError("reviewed site source changed or missing")
    site_document = json.loads(site_source.read_text())
    for key in ("parking_polygon_xy_m", "intersection_polygon_xy_m", "map_name", "map_sha256"):
        if site_document.get(key) != reviewed_site.get(key):
            raise ValueError("reviewed site geometry differs from source")
    native_map = world.get_map()
    if native_map.name != reviewed_site["map_name"]:
        raise ValueError("Native map name differs from reviewed site")
    if hashlib.sha256(native_map.to_opendrive().encode()).hexdigest() != reviewed_site["map_sha256"]:
        raise ValueError("Native OpenDRIVE differs from reviewed site")
    parking = reviewed_site["parking_polygon_xy_m"]
    intersection = reviewed_site["intersection_polygon_xy_m"]
    rows, maps = [], []
    if hasattr(frame_reader, "start"):
        frame_reader.start()
    try:
        commanded = command_lights(vehicle, light_enum, mode)
        for _ in range(ticks):
            vehicle.apply_control(parking_control)
            frame = world.tick()
            snapshot = world.get_snapshot()
            if type(frame) is not int or snapshot.frame != frame:
                raise ValueError("Native world frame mismatch")
            timestamp = float(snapshot.timestamp.elapsed_seconds)
            velocity = vehicle.get_velocity()
            speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
            corners = vehicle.bounding_box.get_world_vertices(vehicle.get_transform())
            if len(corners) < 4:
                raise ValueError("Native body bounding box missing corners")
            # CARLA boxes have eight vertices. Project all eight onto road XY;
            # four unique footprint corners remain after eliminating height.
            xy = list(dict.fromkeys(tuple(_xy(v)) for v in corners))
            if len(xy) != 4:
                raise ValueError("Native body footprint is not four corners")
            footprint = classify_footprint(xy, parking, intersection)
            observed = frame_reader(frame)
            if set(observed) != set(VIEWS) or any(type(observed[v]) is not int for v in VIEWS):
                raise ValueError("original four-camera frame join missing")
            if any(observed[v] != frame for v in VIEWS):
                raise ValueError("original camera frame does not match Native world")
            rows.append({"frame": frame, "time_s": timestamp,
                         "speed_mps": speed, "parking_brake": bool(parking_control.hand_brake),
                         "footprint_inside_reviewed_parking_polygon": footprint["footprint_inside_reviewed_parking_polygon"],
                         "body_corner_inside_intersection_count": footprint["body_corner_inside_intersection_count"],
                         "light_state_bits": int(vehicle.get_light_state()), "actor_id": vehicle.id})
            maps.append({"frame": frame, **{v + "_source_frame": observed[v] for v in VIEWS}})
        if any(rows[i]["frame"] != rows[0]["frame"] + i for i in range(len(rows))):
            raise ValueError("Native frame gap")
        if any(abs(rows[i]["time_s"] - rows[i - 1]["time_s"] - .05) > .01 for i in range(1, len(rows))):
            raise ValueError("Native capture not 20 Hz")
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        for name, values in (("actor-state.jsonl", rows), ("camera-frame-map.jsonl", maps)):
            (root / name).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in values))
        hashes = {name: _sha(root / name) for name in ("actor-state.jsonl", "camera-frame-map.jsonl")}
        media = frame_reader.finish(ticks) if hasattr(frame_reader, "finish") else None
        return {"format": "parked-headlamp-native-source-v1", "case_id": case_id,
                "requested_mode": mode, "commanded": commanded, "frame_count": len(rows),
                "light_masks": {"low_beam": int(light_enum.LowBeam),
                                "high_beam": int(light_enum.HighBeam)},
                "site_source_sha256": reviewed_site["source_sha256"],
                "diagnostic_site": bool(reviewed_site.get("diagnostic_fixture", False)),
                "source_hashes": hashes, "original_camera_media": media,
                "physical_acceptance_claimed": False}
    finally:
        try:
            vehicle.apply_control(parking_control)
        finally:
            if hasattr(frame_reader, "close"):
                frame_reader.close()
