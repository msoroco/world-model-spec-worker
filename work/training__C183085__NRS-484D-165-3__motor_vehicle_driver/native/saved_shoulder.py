"""Join original stopped-vehicle sources without inferring optical compliance."""
import hashlib
import json
import math
from pathlib import Path

from shoulder_lamp_measure import bracket_relation, THRESHOLDS_FT

FRAMES = 600
SOURCES = ("shoulder-lamp-trace.jsonl", "video_frames.jsonl",
           "shoulder_lighting_survey.json", "optical_measurements.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def join(attempt, config, *, allow_fixture=False):
    attempt = Path(attempt)
    paths = {name: attempt / name for name in SOURCES}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
    hashes = {name: sha(path) for name, path in paths.items()}
    trace, mapping = rows(paths[SOURCES[0]]), rows(paths[SOURCES[1]])
    survey = json.loads(paths[SOURCES[2]].read_text())
    optics = json.loads(paths[SOURCES[3]].read_text())
    if len(trace) != FRAMES or len(mapping) != FRAMES:
        raise ValueError("Full 600-frame original trace and frame map required")
    kind = "synthetic_native_sample" if allow_fixture else "original_native_observation"
    survey_kind = "synthetic_native_sample" if allow_fixture else \
        "original_native_shoulder_lighting_survey"
    if survey.get("source_kind") != survey_kind:
        raise ValueError("Original shoulder survey provenance differs")
    if optics.get("source_kind") != kind:
        raise ValueError("Optical measurement provenance differs")
    for key in ("highway_identity_source", "adjacent_paved_shoulder_source",
                "passing_lane_source", "lighting_hours_source", "civil_time_source",
                "ambient_reveal_protocol_source", "front_lamp_protocol_source",
                "rear_lamp_protocol_source"):
        if not survey.get(key):
            raise ValueError("Original shoulder or lighting source missing: " + key)
    if survey.get("passing_traffic_side") not in ("left", "right"):
        raise ValueError("Passing-traffic side source missing")
    if survey.get("optical_target_kind") != config.get("optical_target_kind") or \
            survey.get("target_distance_ft") != config.get("target_distance_ft"):
        raise ValueError("Optical target differs from selected case")
    if optics.get("camera_sources") != ["overview.mkv", "approach.mkv",
                                       "reference_corner.mkv", "driver_reference.mkv"]:
        raise ValueError("Four original camera source references missing")
    brackets = {}
    for key, threshold in THRESHOLDS_FT.items():
        probe = optics.get("probes", {}).get(key)
        if not isinstance(probe, dict) or not probe.get("method_source") or \
                not probe.get("pixel_evidence_source"):
            raise ValueError("Optical probe method or pixel evidence missing: " + key)
        brackets[key] = bracket_relation(probe, threshold)
    prior_native = None
    off_position, off_low_beam, speed_failures = [], [], []
    for index, (row, frame_map) in enumerate(zip(trace, mapping)):
        native = row.get("native_frame")
        if row.get("source_kind") != kind or row.get("frame") != index or \
                row.get("video_frame") != index or frame_map.get("video_frame") != index or \
                frame_map.get("native_frame") != native or \
                frame_map.get("carla_frame") != native or \
                row.get("time_s") != frame_map.get("time_s") or \
                abs(row.get("time_s", -100) - index / 20) > 1e-6:
            raise ValueError("Original Native, video and time join differs")
        if type(native) is not int or (prior_native is not None and native <= prior_native):
            raise ValueError("Original Native frame sequence differs")
        prior_native = native
        speed = row.get("ego_speed_mps")
        if not isinstance(speed, (int, float)) or not math.isfinite(speed):
            raise ValueError("Stopped speed source missing")
        if speed > .05:
            speed_failures.append(index)
        if type(row.get("position_commanded")) is not bool or \
                type(row.get("low_beam_commanded")) is not bool:
            raise ValueError("Lamp command state source missing")
        if not row["position_commanded"]:
            off_position.append(index)
        if not row["low_beam_commanded"]:
            off_low_beam.append(index)
        if row.get("passing_traffic_side") != survey["passing_traffic_side"]:
            raise ValueError("Passing-traffic side source differs")
    return {"case_id": config["case_id"], "source_kind": kind,
            "source_hashes": hashes, "frames": FRAMES,
            "position_command_omission_frames": off_position,
            "low_beam_command_omission_frames": off_low_beam,
            "engineering_stop_failure_frames": speed_failures,
            "optical_brackets": brackets,
            "original_pixels_review_required": True,
            "legal_verdict_claimed": False}
