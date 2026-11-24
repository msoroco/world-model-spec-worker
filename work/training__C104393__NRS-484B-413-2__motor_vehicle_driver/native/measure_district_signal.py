"""Source-bound 100-foot district alternative; unselected CPU preparation only."""

import hashlib
import json
import math
from pathlib import Path

FRAMES = 840
RATE_HZ = 20


def sha256(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Missing source hash: " + name)


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid " + name)
    return float(value)


def measure(context, rows):
    if context.get("source_kind") != "original_native_district_signal_readback":
        raise ValueError("Original district signal readback missing")
    for name in ("native_map_sha256", "land_use_survey_sha256", "frontage_evidence_sha256",
                 "indicator_state_source_sha256", "ego_pose_source_sha256", "course_change_source_sha256",
                 "weather_source_sha256"):
        sha256(context.get(name), name)
    if context.get("district_class") not in {"business", "residential"} or context.get("district_survey_verified") is not True:
        raise ValueError("Business or residential district not sourced")
    if context.get("turn_direction") not in {"left", "right"}:
        raise ValueError("Turn direction missing")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 42-second Native trace")
    prior_native = None
    positions = []
    signals = []
    turns = []
    weather = set()
    for i, row in enumerate(rows):
        if row.get("video_frame") != i:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (prior_native is not None and native <= prior_native):
            raise ValueError("Native frame identity gap")
        prior_native = native
        if abs(finite(row.get("time_s"), "Native time") - i / RATE_HZ) > 1e-6:
            raise ValueError("Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != {"overview", "approach", "reference_corner", "driver_reference"} or any(v != i for v in cameras.values()):
            raise ValueError("Four source camera frame join failed")
        if row.get("district_class") != context["district_class"]:
            raise ValueError("District source changed during approach")
        if row.get("indicator") not in {"left", "right", "off"} or type(row.get("course_change")) is not bool:
            raise ValueError("Indicator or course-change state missing")
        xy = row.get("ego_xy_m")
        if not isinstance(xy, list) or len(xy) != 2:
            raise ValueError("Observed ego pose missing")
        positions.append(tuple(finite(v, "ego pose") for v in xy))
        signals.append(row["indicator"])
        if row["course_change"]:
            turns.append(i)
        if not isinstance(row.get("weather"), str) or not row["weather"]:
            raise ValueError("Weather source missing")
        weather.add(row["weather"])
    if len(turns) != 1 or turns[0] < 2:
        raise ValueError("One observed course change required")
    turn = turns[0]
    direction = context["turn_direction"]
    start = turn
    while start > 0 and signals[start - 1] == direction:
        start -= 1
    if start == 0 or signals[start - 1] != "off" or signals[turn] != direction:
        raise ValueError("Continuous signal onset not captured")
    distance = 0.0
    for i in range(start + 1, turn + 1):
        step = math.dist(positions[i - 1], positions[i])
        if not 0 < step < 1:
            raise ValueError("Implausible observed path step")
        distance += step
    return {"format": "worker-source-district-signal-distance-v1",
            "frame_count": FRAMES, "rate_hz": RATE_HZ,
            "source_district_class": context["district_class"],
            "turn_direction": direction, "signal_onset_frame": start,
            "course_change_frame": turn, "continuous_signal_distance_ft": distance / 0.3048,
            "statutory_district_distance_ft": 100, "observed_weather_states": sorted(weather),
            "legal_compliance": "unassessed", "original_native_observed": False,
            "limitations": ["District classification and frontage require original source and independent review.",
                            "Sampled path distance does not substitute for original visible indicator and course-change pixel review.",
                            "The same signal duty applies regardless of weather; weather is recorded, not a waiver."]}


def measure_file(context_path, rows_path):
    context = json.loads(Path(context_path).read_text())
    raw = Path(rows_path).read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line]
    result = measure(context, rows)
    result["source_sha256"] = hashlib.sha256(raw).hexdigest()
    result["context_sha256"] = hashlib.sha256(Path(context_path).read_bytes()).hexdigest()
    return result
