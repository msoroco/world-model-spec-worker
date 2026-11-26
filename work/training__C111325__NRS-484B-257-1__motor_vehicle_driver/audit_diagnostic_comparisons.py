"""Independent fixed-source comparison checks over saved packet observations."""

import hashlib
import json

from measure_statutory import measure

BASE = "training__C111325__NRS-484B-257-1__motor_vehicle_driver__"
FIXED_SOURCES = ("map", "through_road", "ego_body", "through_body")


def motion_hash(rows, fields):
    serial = [[row[field] for field in fields] for row in rows]
    return hashlib.sha256(json.dumps(serial, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def record(context, rows, case_id):
    observation = measure(context, rows, case_id)
    return {
        "context": context,
        "observation": observation,
        "ego_motion_sha256": motion_hash(rows, ("ego_x_m", "ego_speed_mps")),
        "through_motion_sha256": motion_hash(rows, ("through_y_m", "through_speed_mps")),
    }


def audit(comparison, records, require_original=True):
    cid = comparison.get("comparison_id", "")
    if not cid.startswith(BASE) or set(comparison.get("case_ids", [])) != set(records) or len(records) < 2:
        raise ValueError("Comparison exact case identities differ")
    short = cid[len(BASE):]
    if short not in {"comparison", "yield_sign_action", "stopping_reference", "yield_reference", "through_vehicle_phase",
                     "crossing_interval", "police_exception", "signal_exception"}:
        raise ValueError("Unknown statutory comparison")
    values = list(records.values())
    if require_original and any(v["observation"]["source_kind"] != "original_native_readback" for v in values):
        raise ValueError("Original Native source required for delivery comparison")
    for case_id, value in records.items():
        if value["observation"].get("case_id") != case_id or value["context"].get("case_id") != case_id:
            raise ValueError("Comparison observation case identity differs")
        if value["observation"].get("legal_verdict") is not None or value["observation"].get("sample_count") != 600:
            raise ValueError("Comparison source history or legal separation differs")
    for name in FIXED_SOURCES:
        if len({value["observation"]["source_hashes"][name] for value in values}) != 1:
            raise ValueError("Fixed source changed: " + name)
    if len({value["observation"]["source_hashes"]["sign"] for value in values}) != 1:
        raise ValueError("Governing sign source changed")
    if short not in {"stopping_reference", "yield_reference"} and len({value["observation"]["source_hashes"]["reference"] for value in values}) != 1:
        raise ValueError("Stopping reference changed outside hierarchy comparison")
    control_sources = {value["observation"]["source_hashes"]["controls"] for value in values}
    if short not in {"police_exception", "signal_exception"} and len(control_sources) != 1:
        raise ValueError("Control source changed outside exception comparison")
    ego_motion = {value["ego_motion_sha256"] for value in values}
    through_motion = {value["through_motion_sha256"] for value in values}
    if short in {"comparison", "yield_sign_action", "stopping_reference", "yield_reference"}:
        if len(through_motion) != 1:
            raise ValueError("Through-highway motion changed in subject/reference comparison")
        if short not in {"stopping_reference", "yield_reference"} and len(ego_motion) < 2:
            raise ValueError("Subject action did not vary")
    elif short in {"through_vehicle_phase", "crossing_interval"}:
        if len(ego_motion) != 1 or len(through_motion) < 2:
            raise ValueError("Through-vehicle phase isolation failed")
    else:
        if len(ego_motion) != 1 or len(through_motion) != 1 or len(control_sources) < 2:
            raise ValueError("Controlling exception isolation failed")
    observations = [v["observation"] for v in values]
    if short in {"comparison", "yield_sign_action"}:
        if len({bool(v["rest_frames_before_reference"]) for v in observations}) < 2:
            raise ValueError("Stop/slow action comparison not observable")
    elif short in {"stopping_reference", "yield_reference"}:
        if len({v["stopping_reference"] for v in observations}) != 3:
            raise ValueError("Three hierarchy references not observed")
    elif short == "through_vehicle_phase":
        if len({bool(v["through_approaching_while_crossing_frames"]) for v in observations}) < 2:
            raise ValueError("Approaching through-vehicle difference not observed")
    elif short == "crossing_interval":
        if len({bool(v["simultaneous_occupancy_frames"]) for v in observations}) < 2:
            raise ValueError("Across/within occupancy difference not observed")
    else:
        if len({v["controlling_exception"] for v in observations}) < 2:
            raise ValueError("Control exception not observed")
    return {"comparison_id": cid, "case_ids": sorted(records),
            "source_kind": "original_native_readback" if require_original else "synthetic_diagnostic",
            "fixed_source_checks_passed": True,
            "legal_verdict": None, "physical_acceptance_claimed": False}
