"""Source-bound pedestrian encounter diagnostics; no legal due-care verdict."""

import hashlib
import json
import math

FRAMES = 600
RATE = 20


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(packet):
    require(packet.get("format") == "worker-pedestrian-due-care-source-v1", "Wrong packet format")
    require(packet.get("law_id") == "NRS-484B-280-1a" and packet.get("cell_id") == "C230266", "Wrong law or cell")
    require(packet.get("source_kind") in ("original_native_observation", "synthetic_native_sample"), "Unknown source kind")
    require(packet.get("actor") == "motor_vehicle_driver" and packet.get("vehicle_id") and packet.get("pedestrian_id")
            and packet["vehicle_id"] != packet["pedestrian_id"], "Distinct motor vehicle and pedestrian required")
    require(packet.get("vehicle_classification_source") and packet.get("pedestrian_classification_source")
            and packet.get("path_survey_source"), "Actor classification and independent path survey required")
    rows = packet.get("trace")
    require(isinstance(rows, list) and len(rows) == FRAMES, "Full 600-frame trace required")
    require(digest(rows) == packet.get("trace_sha256"), "Trace hash mismatch")
    gaps, speeds, ttcs, contacts, decels, conflict = [], [], [], [], [], []
    for i, row in enumerate(rows):
        require(row.get("frame") == i and row.get("video_frame") == i
                and type(row.get("native_frame")) is int and number(row.get("time_s"))
                and abs(row["time_s"] - i / RATE) < 1e-8, "Native, video and time join required")
        for key in ("vehicle_x_m", "vehicle_y_m", "pedestrian_x_m", "pedestrian_y_m",
                    "vehicle_speed_mps", "pedestrian_speed_mps", "vehicle_radius_m", "pedestrian_radius_m"):
            require(number(row.get(key)), "Measured pose, speed and body dimensions required")
        require(row["vehicle_speed_mps"] >= 0 and row["pedestrian_speed_mps"] >= 0
                and row["vehicle_radius_m"] > 0 and row["pedestrian_radius_m"] > 0,
                "Invalid measured speed or body dimensions")
        require(type(row.get("contact_sensor")) is bool and row.get("contact_source"), "Contact source required")
        require(type(row.get("path_conflict_survey")) is bool, "Independent path conflict survey required")
        require(type(row.get("requested_brake")) in (int, float) and 0 <= row["requested_brake"] <= 1,
                "Requested control required")
        dx = row["pedestrian_x_m"] - row["vehicle_x_m"]
        dy = row["pedestrian_y_m"] - row["vehicle_y_m"]
        gap = max(0.0, math.hypot(dx, dy) - row["vehicle_radius_m"] - row["pedestrian_radius_m"])
        gaps.append(gap)
        speeds.append(row["vehicle_speed_mps"])
        contacts.append(row["contact_sensor"])
        conflict.append(row["path_conflict_survey"])
        if i:
            decels.append((speeds[i - 1] - speeds[i]) * RATE)
        closing = row["vehicle_speed_mps"] - row["pedestrian_speed_mps"]
        ttcs.append(dx / closing if dx > 0 and closing > 0 and row["path_conflict_survey"] else None)
    require(any(conflict), "No surveyed pedestrian path conflict")
    require(any(gaps[i + 1] < gaps[i] for i in range(FRAMES - 1))
            and any(gaps[i + 1] > gaps[i] for i in range(FRAMES - 1)), "Approach and separation both required")
    return {
        "format": "worker-pedestrian-due-care-measurement-v1",
        "source_kind": packet["source_kind"], "trace_sha256": packet["trace_sha256"],
        "frames": FRAMES, "rate_hz": RATE,
        "first_conflict_frame": conflict.index(True), "conflict_frames": sum(conflict),
        "minimum_surface_gap_m": min(gaps), "contact_frames": sum(contacts),
        "minimum_nonnegative_time_to_conflict_s": min((x for x in ttcs if x is not None), default=None),
        "peak_measured_deceleration_mps2": max(decels),
        "speed_first_conflict_mps": speeds[conflict.index(True)],
        "speed_at_min_gap_mps": speeds[gaps.index(min(gaps))],
        "requested_brake_frames": sum(row["requested_brake"] > 0 for row in rows),
        "actual_native_observed": packet["source_kind"] == "original_native_observation",
        "legal_due_care_verdict": None, "physical_completion": False,
    }
