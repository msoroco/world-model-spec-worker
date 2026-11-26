"""Saved measurement from source-sealed Native crossing samples.

Twenty feet is an arithmetic reference. A measured geometric distance does not
resolve the legal measurement convention, halt category or exception judgment.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import crosswalk_clearance as geometry
import crosswalk_site as crossing


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_file(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def measure(root, case_id, *, diagnostic=False):
    root = Path(root)
    site_path = require_file(root, "original-site.json")
    history_path = require_file(root, "original-crosswalk-history.json")
    site = json.loads(site_path.read_text())
    packet = json.loads(history_path.read_text())
    tag = case_id.removeprefix(crossing.ASSIGNMENT_ID + "__")
    controls = crossing.CASE_CONTROLS.get(tag)
    crossing.require(case_id.startswith(crossing.ASSIGNMENT_ID + "__") and
                     controls is not None, "unknown exact crossing case")
    expected_kind = "diagnostic_fixture" if diagnostic else "original_native"
    if not diagnostic:
        crossing.load_site(site_path, sha(site_path), case_id)
    crossing.require(packet.get("source_kind") == expected_kind and
                     packet.get("diagnostic_fixture") is diagnostic and
                     packet.get("assignment_id") == crossing.ASSIGNMENT_ID and
                     packet.get("case_id") == case_id and
                     packet.get("site_sha256") == sha(site_path),
                     "source-sealed original or diagnostic crossing packet required")
    crossing.require(site.get("requested_activity") == controls[1] and
                     site.get("requested_exception") == controls[2] and
                     site.get("crosswalk_marked") is controls[3],
                     "source crossing context changed")
    crossing.require(packet.get("fps") == 20 and
                     packet.get("frame_count") == len(packet.get("samples", [])) and
                     len(packet["samples"]) == (9 if diagnostic else 900),
                     "original 20 Hz full-duration crossing trace required")
    crossing.require(set(packet.get("camera_archives", {})) == set(
        ("overview", "approach", "reference_corner", "driver_reference")),
        "original four-camera inventory incomplete")
    for view, item in packet["camera_archives"].items():
        path = require_file(root, item["path"])
        if diagnostic:
            crossing.require(item.get("path") == view + ".mkv",
                             "diagnostic camera video identity changed: " + view)
        else:
            crossing.require(item.get("sha256") == sha(path) and
                             item.get("frame_count") == len(packet["samples"]),
                             "original camera archive changed: " + view)
    crossing_polygon = geometry.polygon(site.get("crossing_polygon_xy_m"))
    rows = packet["samples"]
    start_frame = rows[0].get("frame")
    start_time = rows[0].get("time_s")
    crossing.require(type(start_frame) is int and
                     type(start_time) in (int, float) and math.isfinite(start_time),
                     "original frame identity missing")
    samples = []
    for index, row in enumerate(rows):
        crossing.require(row.get("frame") == start_frame + index and
                         isinstance(row.get("time_s"), (int, float)) and
                         abs(row["time_s"] - start_time - index / 20) < .005,
                         "original frame/time join invalid")
        crossing.require(row.get("road_id") == site.get("road_id") and
                         row.get("lane_id") == site.get("lane_id"),
                         "original approach lane changed")
        crossing.require(row.get("activity_readback") == controls[1] and
                         row.get("exception_readback") == controls[2],
                         "original activity or exception readback changed")
        speed = row.get("ego_speed_mps")
        crossing.require(type(speed) in (int, float) and math.isfinite(speed) and
                         speed >= 0, "original ego speed missing")
        body = geometry.polygon(row.get("ego_body_polygon_xy_m"))
        cameras = row.get("camera_frames", {})
        crossing.require(set(cameras) == set(packet["camera_archives"]),
                         "original synchronized camera frame missing")
        for view, camera in cameras.items():
            crossing.require(camera.get("member") == f'{row["frame"]:08d}.png' and
                             isinstance(camera.get("sha256"), str) and
                             len(camera["sha256"]) == 64,
                             "original camera frame identity differs: " + view)
        samples.append({"frame": row["frame"], "time_s": row["time_s"],
                        "speed_mps": speed,
                        "body_clearance_m": geometry.clearance(body, crossing_polygon)})
    minimum = min(samples, key=lambda row: row["body_clearance_m"])
    stopped_samples = [sample["frame"] for sample in samples if sample["speed_mps"] == 0]
    return {"case_id": case_id,
            "source_kind": expected_kind, "diagnostic_fixture": diagnostic,
            "frame_count": len(samples), "body_clearance_min_m": minimum["body_clearance_m"],
            "minimum_clearance_frame": minimum["frame"],
            "stationary_sample_frames": stopped_samples,
            "requested_clearance_m": controls[0],
            "twenty_feet_m_arithmetic_reference": geometry.TWENTY_FEET_M,
            "source_hashes": {"original-site.json": sha(site_path),
                              "original-crosswalk-history.json": sha(history_path)},
            "crosswalk_marked": controls[3], "requested_activity": controls[1],
            "requested_exception": controls[2],
            "legal_measurement_convention": "unresolved",
            "stop_stand_park_judgment": "unresolved",
            "exception_judgment": "unresolved",
            "physical_acceptance": "unverified"}
