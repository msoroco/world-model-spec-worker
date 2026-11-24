"""Measure speed against source-surveyed default or posted-limit stretches."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "ego_front", "roadside_sign", "rear"}
MPH_TO_MPS = 0.44704
DEFAULT_MPH = 25.0


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def measure(context, rows):
    if context.get("source_kind") != "native_speed_and_complete_sign_survey":
        raise ValueError("Missing Native speed and complete sign survey")
    for key in ("native_map_sha256", "street_status_sha256", "sign_survey_sha256"):
        value = context.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"Missing source hash: {key}")
    if context.get("street_status") not in {"city_street", "city_highway"}:
        raise ValueError("Covered street or highway status not sourced")
    surveyed = context.get("surveyed_route_interval_m")
    if not isinstance(surveyed, list) or len(surveyed) != 2:
        raise ValueError("Incomplete sign-survey interval")
    survey_start, survey_end = [finite(x, "survey extent") for x in surveyed]
    if survey_start >= survey_end or context.get("survey_complete_both_directions") is not True:
        raise ValueError("Incomplete sign-survey coverage")
    signs = context.get("applicable_posted_signs")
    if not isinstance(signs, list):
        raise ValueError("Missing posted-sign inventory")
    clean_signs = []
    for sign in signs:
        if not isinstance(sign, dict) or set(sign) != {"governs_from_m", "governs_to_m", "limit_mph", "pixel_sha256"}:
            raise ValueError("Incomplete posted-sign governance")
        a, b, mph = (finite(sign[key], key) for key in ("governs_from_m", "governs_to_m", "limit_mph"))
        source = sign["pixel_sha256"]
        if a >= b or mph <= 0 or not isinstance(source, str) or len(source) != 64:
            raise ValueError("Invalid posted-sign governance")
        clean_signs.append((a, b, mph))
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    previous_native = None
    speeds_mph = []
    governing = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("video_frame") != index:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (previous_native is not None and native <= previous_native):
            raise ValueError("Native frame identity gap")
        previous_native = native
        if abs(finite(row.get("time_s"), "Native time") - index / RATE_HZ) > 1e-6:
            raise ValueError("Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[name] != index for name in CAMERAS):
            raise ValueError("Four source camera frame join failed")
        position = finite(row.get("route_position_m"), "route position")
        speed = finite(row.get("observed_speed_mps"), "original observed speed")
        if speed < 0 or not survey_start <= position <= survey_end:
            raise ValueError("Speed or position outside surveyed route")
        applicable = [mph for a, b, mph in clean_signs if a <= position < b]
        if len(applicable) > 1:
            raise ValueError("Conflicting posted-sign governance")
        governing.append(applicable[0] if applicable else DEFAULT_MPH)
        speeds_mph.append(speed / MPH_TO_MPS)
    return {"format": "worker-source-speed-limit-measurement", "frame_count": FRAMES,
            "rate_hz": RATE_HZ, "observed_speed_mph_range": [min(speeds_mph), max(speeds_mph)],
            "default_governed_frames": sum(limit == DEFAULT_MPH for limit in governing),
            "posted_governed_frames": sum(limit != DEFAULT_MPH for limit in governing),
            "default_frames_above_25_mph": sum(limit == DEFAULT_MPH and speed > DEFAULT_MPH
                                               for limit, speed in zip(governing, speeds_mph)),
            "governing_limit_mph_values": sorted(set(governing)),
            "prima_facie_legal_status": "requires_independent_review",
            "legal_compliance": "unassessed",
            "limitations": ["Complete sign-survey and authority require original source review",
                            "Above-default frames are measurements, not a legal verdict"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    context = json.loads(args.context.read_text())
    rows = [json.loads(line) for line in args.trace.read_text().splitlines() if line]
    args.output.write_text(json.dumps(measure(context, rows), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
