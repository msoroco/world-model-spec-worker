"""Original-frame measurement for NRS 484B.413(2) signal coverage.

This module reports physical observations. It does not decide district status or
make a legal finding. Input must be a sealed Native history with source readback.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


FPS = 20
METRES_PER_FOOT = 0.3048
DISTANCES_FT = {"business": 100, "residential": 100, "other": 300}


class EvidenceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def verify_source_bindings(packet: dict, source_root: Path) -> list[str]:
    """Verify the five input files against a sealed source inventory."""
    root = source_root.resolve()
    sources = packet.get("source_files")
    require(isinstance(sources, dict), "missing source-file inventory")
    required = ("sealed_result", "frame_map", "light_readback", "turn_onset", "district_context")
    for name in required:
        entry = sources.get(name)
        require(isinstance(entry, dict), f"missing {name} source")
        rel = entry.get("path")
        require(isinstance(rel, str) and rel, f"missing {name} path")
        path = (root / rel).resolve()
        require(path.is_relative_to(root), f"source escapes root: {name}")
        require(path.is_file(), f"missing source file: {name}")
        digest = sha256(path.read_bytes()).hexdigest()
        require(digest == entry.get("sha256"), f"stale source hash: {name}")
    require(sources["sealed_result"]["sha256"] == packet.get("sealed_result_sha256"),
            "sealed result binding mismatch")
    require(sources["frame_map"]["sha256"] == packet.get("frame_map_sha256"),
            "frame map binding mismatch")
    sealed = json.loads((root / sources["sealed_result"]["path"]).read_text())
    light = json.loads((root / sources["light_readback"]["path"]).read_text())
    frame_map = json.loads((root / sources["frame_map"]["path"]).read_text())
    onset = json.loads((root / sources["turn_onset"]["path"]).read_text())
    district = json.loads((root / sources["district_context"]["path"]).read_text())
    require(sealed.get("case_id") == packet.get("case_id"),
            "sealed result case identity disagrees with packet")
    require(sealed.get("turn_direction") == packet.get("turn_direction"),
            "sealed result turn direction disagrees with packet")
    for key in ("original_trace_sha256", "original_video_sha256"):
        value = packet.get(key)
        require(isinstance(value, str) and len(value) == 64 and
                all(c in "0123456789abcdef" for c in value),
                f"missing original recording binding: {key}")
        require(sealed.get(key) == value,
                f"sealed result original recording binding disagrees: {key}")
    require(light.get("samples") == packet.get("samples"), "light/position samples disagree with source")
    for key in ("signal_source", "position_source"):
        require(light.get(key) == packet.get(key), f"{key} disagrees with source")
    expected_frames = [{"frame": row.get("frame"), "time_s": row.get("time_s")}
                       for row in packet.get("samples", [])]
    require(frame_map.get("frames") == expected_frames,
            "original frame map disagrees with signal samples")
    require(onset.get("turn_onset_frame") == packet.get("turn_onset_frame"), "turn onset disagrees with source")
    require(onset.get("turn_direction") == packet.get("turn_direction"),
            "observed turn direction disagrees with source")
    require(onset.get("turn_onset_source") == packet.get("turn_onset_source"),
            "turn onset observation source disagrees with source")
    for key in ("district_class", "district_source", "weather"):
        require(district.get(key) == packet.get(key), f"{key} disagrees with source")
    return list(required)


def measure(packet: dict) -> dict:
    """Measure continuous observed signal length before observed course change.

    Samples cover frame zero through the turn-onset frame without gaps. Position
    is the original Native world position in metres; signal is a vehicle-light
    readback, not a controller command. The independently observed turn onset is
    bound to its original frame and source path. Context classification remains
    explicitly sourced and unresolved by this physical measurement.
    """
    require(packet.get("format") == "original-signal-history-v1", "history format")
    require(packet.get("fps") == FPS, "history must use 20 Hz")
    require(packet.get("sealed_result_sha256"), "missing sealed result hash")
    require(packet.get("frame_map_sha256"), "missing original frame map hash")
    for key in ("original_trace_sha256", "original_video_sha256"):
        value = packet.get(key)
        require(isinstance(value, str) and len(value) == 64 and
                all(c in "0123456789abcdef" for c in value),
                f"missing original recording binding: {key}")
    require(packet.get("signal_source") == "vehicle_light_state_readback", "signal must be observed readback")
    require(packet.get("position_source") == "native_actor_transform", "position must be original Native transform")
    require(packet.get("turn_onset_source"), "missing independent turn-onset source")
    district = packet.get("district_class")
    require(district in DISTANCES_FT, "district class must be sourced")
    require(packet.get("district_source"), "missing district-class source")
    direction = packet.get("turn_direction")
    require(direction in ("left", "right"), "turn direction")
    samples = packet.get("samples")
    require(isinstance(samples, list) and len(samples) >= 3, "missing samples")
    first_time = samples[0].get("time_s") if isinstance(samples[0], dict) else None
    require(isinstance(first_time, (int, float)) and not isinstance(first_time, bool) and
            isfinite(first_time) and first_time >= 0, "invalid original first-frame time")
    onset = packet.get("turn_onset_frame")
    require(isinstance(onset, int) and not isinstance(onset, bool) and onset >= 2,
            "missing observed turn onset")
    require(onset < len(samples), "turn onset outside samples")
    for i, s in enumerate(samples):
        require(isinstance(s, dict), "original signal sample must be an object")
        require(isinstance(s.get("frame"), int) and not isinstance(s["frame"], bool) and
                s["frame"] == i, "nonconsecutive original frames")
        sample_time = s.get("time_s")
        require(isinstance(sample_time, (int, float)) and not isinstance(sample_time, bool) and
                isfinite(sample_time) and abs(sample_time - first_time - i / FPS) <= 0.001,
                "frame time disagrees with 20 Hz")
        require(s.get("light_source") == "vehicle_light_state_readback", "command substituted for light readback")
        require(s.get("signal") in ("left", "right", "off"), "missing signal readback")
        for key in ("x_m", "y_m"):
            require(isinstance(s.get(key), (int, float)) and not isinstance(s[key], bool) and
                    isfinite(s[key]), "invalid Native position")
    # A signal in the turn direction must remain observed at every sample of the
    # continuous final interval. The last interruption fixes its start.
    start = onset
    while start > 0 and samples[start - 1]["signal"] == direction:
        start -= 1
    require(samples[onset]["signal"] == direction, "signal absent at turn onset")
    length_m = sum(
        hypot(samples[i]["x_m"] - samples[i - 1]["x_m"],
              samples[i]["y_m"] - samples[i - 1]["y_m"])
        for i in range(start + 1, onset + 1)
    )
    return {
        "continuous_start_frame": start,
        "turn_onset_frame": onset,
        "continuous_distance_m": length_m,
        "continuous_distance_ft": length_m / METRES_PER_FOOT,
        "statutory_reference_ft": DISTANCES_FT[district],
        "district_class": district,
        "turn_direction": direction,
        "weather": packet.get("weather"),
        "sealed_result_sha256": packet["sealed_result_sha256"],
        "frame_map_sha256": packet["frame_map_sha256"],
        "original_trace_sha256": packet["original_trace_sha256"],
        "original_video_sha256": packet["original_video_sha256"],
        "interpretation": "physical measurement only; legal applicability unresolved",
    }


def audit_comparison(left: dict, right: dict, declared_difference: str) -> dict:
    """Reject a purported distance comparison with changed context or capture."""
    require(declared_difference == "signal_activation_distance", "unsupported comparison difference")
    fixed = ("district_class", "district_source", "turn_direction", "route_sha256",
             "map_sha256", "weather", "camera_plan_sha256", "duration_frames",
             "ego_blueprint", "other_vehicle_plan_sha256")
    for key in fixed:
        require(left.get(key) is not None and right.get(key) is not None, f"missing fixed condition: {key}")
        require(left[key] == right[key], f"changed fixed condition: {key}")
    for key in ("route_sha256", "map_sha256", "camera_plan_sha256", "other_vehicle_plan_sha256"):
        value = left[key]
        require(isinstance(value, str) and len(value) == 64 and
                all(c in "0123456789abcdef" for c in value),
                f"invalid fixed source hash: {key}")
    for key in ("district_source", "weather", "ego_blueprint"):
        require(isinstance(left[key], str) and bool(left[key].strip()),
                f"empty fixed condition: {key}")
    require(isinstance(left["duration_frames"], int) and not isinstance(left["duration_frames"], bool)
            and left["duration_frames"] > 0, "invalid fixed duration")
    require(isinstance(left.get("case_id"), str) and bool(left["case_id"].strip()) and
            isinstance(right.get("case_id"), str) and bool(right["case_id"].strip()),
            "missing comparison case identity")
    require(left.get("case_id") != right.get("case_id"), "comparison repeats one case")
    a, b = measure(left), measure(right)
    require(abs(a["continuous_distance_m"] - b["continuous_distance_m"]) > 0.01,
            "declared signal-distance difference not measured")
    return {"case_ids": [left["case_id"], right["case_id"]],
            "distances_ft": [a["continuous_distance_ft"], b["continuous_distance_ft"]],
            "fixed_conditions_checked": list(fixed), "interpretation": "physical comparison only"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit sealed original signal histories")
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    left = json.loads(args.packet.read_text())
    left_sources = verify_source_bindings(left, args.source_root)
    if args.compare:
        right = json.loads(args.compare.read_text())
        right_sources = verify_source_bindings(right, args.source_root)
        value = audit_comparison(left, right, "signal_activation_distance")
        value["verified_source_files"] = {"left": left_sources, "right": right_sources}
    else:
        value = measure(left)
        value["verified_source_files"] = left_sources
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
