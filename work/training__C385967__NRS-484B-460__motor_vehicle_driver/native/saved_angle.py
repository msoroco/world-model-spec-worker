"""Measure the original device-to-curb angle only while the vehicle rests."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


FRAMES = 600
HZ = 20
ASSIGNMENT = "training__C385967__NRS-484B-460__motor_vehicle_driver"
CASES = {ASSIGNMENT + "__selected_03f318de__condition_a",
         ASSIGNMENT + "__selected_03f318de__condition_b"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return json.loads(path.read_text())


def read_rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def unsigned_angle_to_edge(heading, edge_heading):
    # An unoriented curb line has the same angle at 0 and 180 degrees.
    return abs((heading - edge_heading + 90) % 180 - 90)


def measure(attempt, case_id, *, allow_fixture=False):
    attempt = Path(attempt)
    if case_id not in CASES:
        raise ValueError("Exact selected case differs")
    names = ("native_samples.jsonl", "body_history.jsonl", "video_frames.jsonl",
             "official_device.json", "road_geometry.json", "parking_context.json")
    hashes = {name: sha(attempt / name) for name in names if (attempt / name).is_file()}
    if set(hashes) != set(names):
        raise ValueError("Missing required source: " + next(n for n in names if n not in hashes))
    samples, bodies, frames = (read_rows(attempt / name) for name in names[:3])
    device, road, context = (read_json(attempt / name) for name in names[3:])
    if any(len(rows) != FRAMES for rows in (samples, bodies, frames)):
        raise ValueError("Full 600-frame source sequence required")
    provenance = "synthetic_cpu_fixture" if allow_fixture else "original_native_capture"
    if any(obj.get("provenance") != provenance for obj in (device, road, context)):
        raise ValueError("Device, curb or context provenance differs")
    if device.get("official_device_review_required") is not True or \
            device.get("governs_space_id") != context.get("space_id") or \
            device.get("native_road_id") != road.get("native_road_id") or \
            not finite(device.get("indicated_angle_to_curb_deg")):
        raise ValueError("Governing official angle device source absent")
    if not finite(road.get("curb_tangent_heading_deg")) or \
            road.get("curb_side") != "right" or \
            road.get("space_id") != context.get("space_id"):
        raise ValueError("Original curb or highway-edge source absent")
    if context.get("case_id") != case_id or context.get("activity") not in \
            ("stopped", "standing", "parked"):
        raise ValueError("Original stop, stand or park context absent")
    angle = device["indicated_angle_to_curb_deg"]
    if not 0 <= angle <= 90:
        raise ValueError("Device angle outside unoriented curb interval")
    measured = []
    rest_run = 0
    max_rest_run = 0
    for i, (sample, body, frame) in enumerate(zip(samples, bodies, frames)):
        if any(row.get("case_id") != case_id for row in (sample, body, frame)) or \
                any(row.get("provenance") != provenance for row in (sample, body, frame)):
            raise ValueError("Original case or provenance source differs")
        native = sample.get("native_frame")
        if not isinstance(native, int) or native < 0 or \
                sample.get("sample_index") != i or frame.get("video_frame") != i or \
                body.get("native_frame") != native or frame.get("native_frame") != native or \
                frame.get("carla_frame") != native:
            raise ValueError("Original Native/body/camera frame join differs")
        times = [row.get("time_s") for row in (sample, body, frame)]
        if not all(finite(t) for t in times) or max(times) - min(times) > .001 or \
                (i and abs(times[0] - samples[i-1]["time_s"] - 1/HZ) > .002):
            raise ValueError("Original Native/body/camera time join differs")
        if sample.get("native_road_id") != road["native_road_id"] or \
                sample.get("space_id") != context["space_id"]:
            raise ValueError("Ego occupancy source differs from governed highway space")
        heading, speed = sample.get("ego_heading_deg"), sample.get("ego_speed_mps")
        if not finite(heading) or not finite(speed) or speed < 0:
            raise ValueError("Original ego heading or speed readback absent")
        vertices = body.get("body_vertices_m")
        if not isinstance(vertices, list) or len(vertices) < 4 or \
                any(not isinstance(v, list) or len(v) != 3 or not all(finite(x) for x in v)
                    for v in vertices):
            raise ValueError("Original ego body polygon absent")
        if speed <= .1 and sample.get("activity") == context["activity"]:
            measured.append(unsigned_angle_to_edge(heading, road["curb_tangent_heading_deg"]))
            rest_run += 1
            max_rest_run = max(max_rest_run, rest_run)
        else:
            rest_run = 0
    if max_rest_run < HZ:
        raise ValueError("Contiguous at-rest source interval absent")
    return {"format": "c385967-source-bound-angle-measurement-v1",
            "case_id": case_id, "source_kind": provenance,
            "source_hashes": hashes, "frames": FRAMES,
            "at_rest_frames": len(measured), "longest_at_rest_run": max_rest_run,
            "device_indicated_angle_deg": angle,
            "mean_measured_angle_to_curb_deg": sum(measured)/len(measured),
            "maximum_absolute_difference_deg": max(abs(value-angle) for value in measured),
            "legal_tolerance_asserted": False, "physical_acceptance_claimed": False}
