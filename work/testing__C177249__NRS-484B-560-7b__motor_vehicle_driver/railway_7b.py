"""Original-source railway instruction and movement measurements for 484B.560(7)(b).

This module reports observed instruction and response pairs. Official status and
legal obedience remain questions for independent review of the original sources.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

LAW = "NRS-484B-560-7b"
CELL = "C177249"
ACTOR = "motor_vehicle_driver"
CASES = {
    "device_stop_halt": ("device", "stop", "halt"),
    "device_stop_cross": ("device", "stop", "cross"),
    "device_clear_cross": ("device", "clear", "cross"),
    "device_clear_halt": ("device", "clear", "halt"),
    "officer_stop_halt": ("officer", "stop", "halt"),
    "officer_stop_cross": ("officer", "stop", "cross"),
}


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("missing finite original value: " + name)
    return float(value)


def load_packet(path: str | Path, expected_sha256: str):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("reviewed packet hash mismatch")
    packet = json.loads(raw)
    packet["_packet_sha256"] = expected_sha256
    return packet


def validate_site(site: dict, case_name: str):
    if case_name not in CASES:
        raise ValueError("unselected railway instruction case")
    if (site.get("law_id"), site.get("cell_id"), site.get("actor")) != (LAW, CELL, ACTOR):
        raise ValueError("railway source identity mismatch")
    if (site.get("layout"), site.get("maneuver"), site.get("control")) != ("paved_road", "cross_railway", "traffic_control_device"):
        raise ValueError("frozen crossing cell mismatch")
    crossing = site.get("crossing")
    if not isinstance(crossing, dict) or crossing.get("grade_crossing") is not True:
        raise ValueError("source-reviewed railroad crossing required")
    for key in ("rail_geometry_ref", "road_geometry_ref", "approach_lane_ref", "crossing_entry_ref", "crossing_exit_ref"):
        if not crossing.get(key):
            raise ValueError("railway geometry source missing: " + key)
    vehicle = site.get("vehicle")
    if not isinstance(vehicle, dict) or vehicle.get("driver_role") != ACTOR:
        raise ValueError("actual vehicle driver source required")
    for key in ("blueprint_id", "blueprint_source_ref", "actor_id", "driver_identity_ref"):
        if not vehicle.get(key):
            raise ValueError("vehicle or driver source missing: " + key)
    device = site.get("device")
    if not isinstance(device, dict):
        raise ValueError("actual official device inventory required")
    for key in ("actor_or_map_id", "device_type", "placement_ref", "erection_authority_ref", "traffic_purpose_ref", "governed_movement_ref", "instruction_source_ref"):
        if not device.get(key):
            raise ValueError("device officiality or instruction source missing: " + key)
    axis, instruction, response = CASES[case_name]
    case = site.get("case")
    if not isinstance(case, dict) or (case.get("name"), case.get("authority"), case.get("instruction"), case.get("response")) != (case_name, axis, instruction, response):
        raise ValueError("selected instruction construction mismatch")
    if axis == "officer":
        officer = site.get("officer")
        if not isinstance(officer, dict) or not all(officer.get(k) for k in ("actor_id", "identity_ref", "position_ref", "direction_channel_ref")):
            raise ValueError("actual police officer and direction source required")
    return site


def measure(site: dict, rows: list[dict]):
    """Join every original 20 Hz frame to authority, indication and body history."""
    if not rows:
        raise ValueError("original instruction history missing")
    case_name = site["case"]["name"]
    validate_site(site, case_name)
    authority, intended_instruction, _ = CASES[case_name]
    samples = []
    previous_frame = previous_time = None
    for row in rows:
        frame = row.get("source_frame")
        time_s = _number(row.get("time_s"), "frame time")
        if type(frame) is not int or (previous_frame is not None and frame != previous_frame + 1):
            raise ValueError("original frame sequence incomplete")
        if previous_time is not None and not .049 <= time_s - previous_time <= .051:
            raise ValueError("original frame cadence is not 20 Hz")
        previous_frame, previous_time = frame, time_s
        if row.get("source_site_sha256") != site.get("_packet_sha256"):
            raise ValueError("original frame not joined to reviewed site")
        for key in ("device_indication_source_ref", "device_instruction_source_ref", "governed_movement_source_ref", "body_source_ref", "control_source_ref", "crossing_geometry_source_ref"):
            if not row.get(key):
                raise ValueError("original frame source missing: " + key)
        indication = row.get("device_indication")
        if indication not in ("stop", "clear", "unresolved"):
            raise ValueError("original device indication missing")
        officer_direction = row.get("officer_direction")
        if authority == "officer":
            if officer_direction not in ("stop", "clear") or not row.get("officer_direction_source_ref"):
                raise ValueError("original officer direction missing")
        instruction = officer_direction if authority == "officer" else indication
        if instruction != intended_instruction:
            raise ValueError("constructed instruction not maintained in original window")
        front_gap_m = _number(row.get("front_body_gap_to_entry_m"), "crossing entry body gap")
        rear_gap_m = _number(row.get("rear_body_gap_to_exit_m"), "crossing exit body gap")
        speed_mps = _number(row.get("speed_mps"), "actual vehicle speed")
        if speed_mps < 0:
            raise ValueError("negative actual speed")
        samples.append({"source_frame": frame, "time_s": time_s,
                        "device_indication": indication, "officer_direction": officer_direction,
                        "governing_instruction": instruction,
                        "front_body_gap_to_entry_m": front_gap_m,
                        "rear_body_gap_to_exit_m": rear_gap_m,
                        "speed_mps": speed_mps,
                        "brake_applied": row.get("brake_applied")})
    crossed = any(s["front_body_gap_to_entry_m"] <= 0 for s in samples)
    halted_before = any(s["front_body_gap_to_entry_m"] > 0 and s["speed_mps"] <= .1 for s in samples)
    return {"samples": samples, "authority_channel": authority,
            "observed_crossing_entry": crossed, "observed_halt_before_entry": halted_before,
            "observed_full_exit": any(s["rear_body_gap_to_exit_m"] >= 0 for s in samples),
            "device_officiality": "requires independent source review",
            "officer_direction_authenticity": "requires independent source review" if authority == "officer" else "not selected",
            "legal_judgment": "unresolved"}
