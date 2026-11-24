"""Independent saved-source comparison audit for the C110969 case plan.

Inputs are post-capture measurements and a separate source-hashed context packet.
The audit checks comparison isolation and evidence presence, not legal necessity.
"""

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C110969__LVMC-11-52-130-A11__motor_vehicle_driver"
SUFFIXES = ("stop_14ft", "stop_15ft", "stop_16ft", "stand_14ft",
            "traffic_14ft", "police_14ft", "device_14ft")
FIXED = ("map_sha256", "intersection_boundary_sha256", "vehicle_blueprint",
         "vehicle_length_m", "vehicle_width_m", "approach", "route_sha256",
         "camera_plan_sha256", "duration_s", "fps")


def _source(root, source):
    relative = Path(source["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Source path must remain within saved package")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Saved source missing or outside package")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != source["sha256"]:
        raise ValueError("Saved source hash mismatch")
    return json.loads(path.read_text())


def audit(packet_path):
    packet_path = Path(packet_path)
    packet = json.loads(packet_path.read_text())
    if packet.get("assignment_id") != ASSIGNMENT:
        raise ValueError("Assignment identity mismatch")
    rows = {}
    for item in packet["cases"]:
        case_id = item["case_id"]
        if case_id not in {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES} or case_id in rows:
            raise ValueError("Unknown or duplicate case ID")
        measurement = _source(packet_path.parent, item["measurement_source"])
        context = _source(packet_path.parent, item["context_source"])
        if measurement.get("case_id") != case_id or context.get("case_id") != case_id:
            raise ValueError("Saved source case binding mismatch")
        if measurement.get("original_frame_count") != 900 or not measurement.get("pose_sha256"):
            raise ValueError("Original measurement missing")
        if measurement.get("map_sha256") != context.get("map_sha256"):
            raise ValueError("Map source differs from measured geometry")
        if not measurement.get("halt_intervals") or measurement.get("halt_frame_count", 0) < 40:
            raise ValueError("Contiguous halt evidence missing")
        if context.get("diagnostic_fixture") is not False:
            raise ValueError("Diagnostic or unclassified source cannot establish delivery comparison")
        if not context.get("observation_source"):
            raise ValueError("Observed traffic and direction context source missing")
        observation = _source(packet_path.parent, context["observation_source"])
        observed_frames = observation.get("frames") if isinstance(observation, dict) else None
        if (not isinstance(observation, dict) or
                observation.get("cause_observed") != context.get("halt_cause") or
                not isinstance(observed_frames, list) or len(observed_frames) < 2 or
                observed_frames[0] != 0 or observed_frames[-1] != 899 or
                any(type(frame) is not int for frame in observed_frames) or
                any(right <= left for left, right in zip(observed_frames, observed_frames[1:]))):
            raise ValueError("Observed cause or frame coverage differs from context")
        context["context_source_sha256"] = context["observation_source"]["sha256"]
        for key in FIXED:
            if context.get(key) in (None, ""):
                raise ValueError("Fixed context missing: " + key)
        for key, value in (("duration_s", 45), ("fps", 20)):
            if context[key] != value:
                raise ValueError("Capture contract mismatch: " + key)
        gap = measurement.get("minimum_halt_body_gap_m")
        if not isinstance(gap, (int, float)) or not math.isfinite(gap) or gap < 0:
            raise ValueError("Measured gap invalid")
        rows[case_id.removeprefix(ASSIGNMENT + "__")] = (measurement, context)
    if set(rows) != set(SUFFIXES):
        raise ValueError("Seven exact case measurements required")
    baseline = rows["stop_14ft"][1]
    for suffix, (_, context) in rows.items():
        if any(context[key] != baseline[key] for key in FIXED):
            raise ValueError("Fixed condition changed in " + suffix)
        expected_activity = "stand" if suffix == "stand_14ft" else "stop"
        if context.get("activity") != expected_activity:
            raise ValueError("Activity contrast is not isolated")
        expected_cause = {"traffic_14ft": "traffic_conflict_necessity",
                          "police_14ft": "police_direction_necessity",
                          "device_14ft": "device_direction_necessity"}.get(suffix, "ordinary_destination")
        if context.get("halt_cause") != expected_cause:
            raise ValueError("Exception cause contrast is not isolated")
        expected_target = {"stop_15ft": 15, "stop_16ft": 16}.get(suffix, 14)
        if context.get("requested_front_body_gap_ft") != expected_target:
            raise ValueError("Requested numeric probe mismatch")
    for suffix in ("stop_14ft", "stop_15ft", "stop_16ft"):
        if rows[suffix][1]["context_source_sha256"] != baseline["context_source_sha256"]:
            raise ValueError("Boundary contrast has changed traffic or directions")
    for suffix in ("stand_14ft",):
        if rows[suffix][1]["context_source_sha256"] != baseline["context_source_sha256"]:
            raise ValueError("Activity contrast has changed traffic or directions")
    return {"assignment_id": ASSIGNMENT, "case_count": len(rows),
            "comparison_ids": ["fifteen_foot_boundary", "stop_vs_stand", "exception_cause"],
            "measured_minimum_gap_m": {suffix: rows[suffix][0]["minimum_halt_body_gap_m"]
                                       for suffix in SUFFIXES},
            "legal_necessity_resolved": False,
            "limitations": ["Observed gap and context require independent physical review.",
                            "A source-hashed direction does not itself establish legal necessity."]}
