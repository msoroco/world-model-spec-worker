"""Source-bound CPU measurement for the proposed 307(9)(b) straight pair.

The caller supplies retained Native samples and the original frame map. This
module never treats a controller target or fixture label as an observation.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from cycle_controller import EGO_FACE, FRAMES, Sample, measure


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError("Missing required original source: " + path.name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) != FRAMES:
        raise ValueError("Original source must have exactly 600 frames: " + path.name)
    return rows


def _finite(value: object, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Invalid original measurement: " + name)
    return float(value)


def _body_front(row: dict, axis: int, sign: int) -> float:
    body = row.get("body_vertices_m")
    if not isinstance(body, list) or len(body) < 4:
        raise ValueError("Original full-body vertices absent")
    coordinates = []
    for vertex in body:
        if not isinstance(vertex, list) or len(vertex) < 2:
            raise ValueError("Original body vertex malformed")
        coordinates.append(sign * _finite(vertex[axis], "body vertex"))
    return max(coordinates)


def analyze(attempt: Path) -> dict:
    attempt = Path(attempt)
    native_path = attempt / "native_samples.jsonl"
    map_path = attempt / "video_frames.jsonl"
    geometry_path = attempt / "road_geometry.json"
    native = _rows(native_path)
    frames = _rows(map_path)
    if not geometry_path.is_file():
        raise ValueError("Missing required source: road_geometry.json")
    geometry = json.loads(geometry_path.read_text())
    if geometry.get("signal_actor_id") is None or geometry.get("cross_signal_actor_id") is None:
        raise ValueError("Native governing signal and cycle source absent")
    if geometry.get("governing_face") != EGO_FACE:
        raise ValueError("Governing red and turn-arrow survey differs")
    if geometry.get("approach_enters_intersection") is not True:
        raise ValueError("Original approach-to-intersection relation absent")
    if geometry.get("stop_reference_kind") not in ("nearest_crosswalk", "stop_sign_or_marking", "intersection_edge"):
        raise ValueError("Original stop-reference hierarchy absent")
    axis = geometry.get("approach_axis")
    sign = geometry.get("approach_sign")
    if axis not in (0, 1) or sign not in (-1, 1):
        raise ValueError("Original approach orientation absent")
    boundary = _finite(geometry.get("stop_reference_coordinate_m"), "stop boundary")
    if geometry.get("other_device_prohibition_survey") is not False:
        raise ValueError("Original other-device survey absent")
    samples = []
    prior_frame = -1
    prior_time = -math.inf
    observed_cycles = 0
    prior_phase = None
    for index, (n, mapping) in enumerate(zip(native, frames)):
        frame = mapping.get("native_frame")
        time = _finite(mapping.get("time_s"), "frame time")
        if type(frame) is not int or frame <= prior_frame or time <= prior_time:
            raise ValueError("Original frame identities or times do not increase")
        if mapping.get("video_frame") != index or n.get("native_frame") != frame:
            raise ValueError("Original Native/video frame join differs")
        if abs(_finite(n.get("time_s"), "Native time") - time) > 1e-4:
            raise ValueError("Original Native/video time join differs")
        if n.get("signal_actor_id") != geometry["signal_actor_id"] or n.get("cross_signal_actor_id") != geometry["cross_signal_actor_id"]:
            raise ValueError("Original governing signal identity differs")
        phase = n.get("cross_phase_observed")
        if prior_phase and phase != prior_phase:
            if (prior_phase, phase) not in (("cross_green", "cross_yellow"), ("cross_yellow", "cross_red"), ("cross_red", "cross_green")):
                raise ValueError("Original device phase order differs")
            if (prior_phase, phase) == ("cross_red", "cross_green"):
                observed_cycles += 1
        if n.get("controller_cycle_count") != observed_cycles:
            raise ValueError("Controller cycle count differs from observed phases")
        if n.get("actor_class_observed") not in ("motorcycle", "moped", "trimobile", "bicycle", "electric_bicycle", "electric_scooter"):
            raise ValueError("Qualified actor source absent")
        if n.get("detector_request_present") is not True or n.get("detector_request_serviced") is not False:
            raise ValueError("Detector command/readback source absent")
        if n.get("other_device_prohibition_observed") is not False:
            raise ValueError("Other-device prohibition source differs")
        front = _body_front(n, axis, sign)
        speed = _finite(n.get("speed_mps"), "Native speed")
        if speed < 0:
            raise ValueError("Negative Native speed")
        samples.append(Sample(index, n.get("ego_face_observed"), phase, speed,
                              boundary - front, n.get("entered_intersection") is True,
                              True, False, n.get("pedestrians_in_crosswalk") is True,
                              n.get("lawful_traffic_conflict") is True))
        prior_frame, prior_time, prior_phase = frame, time, phase
    result = measure(samples)
    if result["entry_frame"] is None:
        raise ValueError("Original straight intersection entry absent")
    entry = result["entry_frame"]
    if not all(not sample.entered_intersection for sample in samples[:entry]):
        raise ValueError("Original intersection entry history differs")
    return {
        "format": "c111071-saved-source-measurement-v1",
        "source_kind": "original_native_required",
        "frame_count": FRAMES,
        "case_observation": result,
        "native_cycle_transition_count": observed_cycles,
        "entry_conflict_clear": result["yield_clear_at_entry"],
        "other_device_prohibition_survey": False,
        "physical_detector_failure_causation_verified": False,
        "legal_verdict_claimed": False,
        "sources": {name: _sha(path) for name, path in (("native_samples.jsonl", native_path),
                                                     ("video_frames.jsonl", map_path),
                                                     ("road_geometry.json", geometry_path))},
    }
