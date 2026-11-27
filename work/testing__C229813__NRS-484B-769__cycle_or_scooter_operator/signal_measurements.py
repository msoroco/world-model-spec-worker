"""Source-bound roadway right-turn and arm-pose audit for NRS 484B.769.

Arm projections are measurements, not a legal form or timing verdict. The
referenced NRS 484B.420 detail is not reconstructed from this fixture.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C229813__NRS-484B-769__cycle_or_scooter_operator"
KINDS = ("bicycle", "electric_bicycle", "electric_scooter")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _point(value, dimensions):
    if not isinstance(value, list) or len(value) != dimensions or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError(f"finite {dimensions}-dimensional point required")
    return value


def _inside(point, polygon):
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            if x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                inside = not inside
    return inside


def validate_context(context, case_id):
    if context.get("case_id") != case_id or not isinstance(context.get("map_sha256"), str) or len(context["map_sha256"]) != 64:
        raise ValueError("exact source-hashed map/case identity required")
    if context.get("operator_vehicle_kind") not in KINDS or not context.get("operator_identity_source"):
        raise ValueError("covered cycle/scooter operator identity required")
    if context.get("roadway_status") != "roadway" or not context.get("highway_status_source"):
        raise ValueError("original highway and roadway status required")
    roadway = context.get("roadway_polygon")
    shoulder = context.get("shoulder_polygon")
    if not isinstance(roadway, list) or len(roadway) < 3 or not isinstance(shoulder, list) or len(shoulder) < 3:
        raise ValueError("roadway and shoulder geometry required")
    roadway = [_point(p, 2) for p in roadway]
    shoulder = [_point(p, 2) for p in shoulder]
    if not context.get("roadway_geometry_source") or not context.get("shoulder_geometry_source"):
        raise ValueError("original roadway/shoulder source required")
    route = context.get("right_turn_route")
    if not isinstance(route, dict) or not route.get("waypoint_source"):
        raise ValueError("source-backed right-turn route required")
    first, last = _point(route.get("first_heading"), 2), _point(route.get("last_heading"), 2)
    if abs(math.hypot(*first) - 1) > .02 or abs(math.hypot(*last) - 1) > .02:
        raise ValueError("right-turn headings must be unit vectors")
    cross = first[0] * last[1] - first[1] * last[0]
    if cross >= -.1:
        raise ValueError("source route does not turn right")
    return roadway, shoulder


def _arm(shoulder, elbow, wrist, heading):
    shoulder, elbow, wrist = (_point(p, 3) for p in (shoulder, elbow, wrist))
    if abs(math.hypot(*heading) - 1) > .02:
        raise ValueError("original heading must be unit length")
    # In right-handed ground coordinates, clockwise from forward is local right.
    right = (heading[1], -heading[0])
    e = [elbow[i] - shoulder[i] for i in range(3)]
    w = [wrist[i] - shoulder[i] for i in range(3)]
    upper = math.dist(shoulder, elbow)
    fore = math.dist(elbow, wrist)
    if upper <= .02 or fore <= .02:
        raise ValueError("original arm joints degenerate")
    return {"elbow_right_m": e[0] * right[0] + e[1] * right[1],
            "wrist_right_m": w[0] * right[0] + w[1] * right[1],
            "wrist_forward_m": w[0] * heading[0] + w[1] * heading[1],
            "wrist_vertical_from_shoulder_m": w[2],
            "upper_arm_length_m": upper, "forearm_length_m": fore}


def measure(*, case_id, context_path, trace_path, receipt_path,
            allow_diagnostic=False):
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact assignment case ID required")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("original source receipt identity mismatch")
    if receipt.get("diagnostic_fixture") and not allow_diagnostic:
        raise ValueError("diagnostic fixture is not delivery evidence")
    if _sha(context_path) != receipt.get("context_sha256") or _sha(trace_path) != receipt.get("trace_sha256"):
        raise ValueError("original source bytes changed")
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    roadway, shoulder = validate_context(context, case_id)
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or len(rows) != receipt.get("frame_count") or receipt.get("fps") != 20:
        raise ValueError("original 20 Hz frame count mismatch")
    observations = []
    previous = None
    for row in rows:
        frame, time_s = row.get("frame"), row.get("time_s")
        if not isinstance(frame, int) or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
            raise ValueError("original frame/time missing")
        if previous is not None and (frame != previous[0] + 1 or abs(time_s - previous[1] - .05) > .002):
            raise ValueError("original frame order or 20 Hz cadence mismatch")
        previous = frame, time_s
        contact = _point(row.get("operator_vehicle_contact_point"), 2)
        heading = _point(row.get("operator_heading"), 2)
        right_arm = row.get("right_arm")
        if not isinstance(right_arm, dict):
            raise ValueError("original right-arm joint source required")
        posture = _arm(right_arm.get("shoulder"), right_arm.get("elbow"), right_arm.get("wrist"), heading)
        observations.append({"frame": frame, "time_s": time_s,
                             "on_roadway": _inside(contact, roadway) and not _inside(contact, shoulder),
                             "operator_heading": heading, "right_arm": posture})
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": _sha(context_path), "trace_sha256": _sha(trace_path),
                                "receipt_sha256": _sha(receipt_path), "native_map_sha256": context["map_sha256"]},
            "operator_vehicle_kind": context["operator_vehicle_kind"],
            "roadway_frames": [r["frame"] for r in observations if r["on_roadway"]],
            "shoulder_or_off_roadway_frames": [r["frame"] for r in observations if not r["on_roadway"]],
            "observations": observations, "signal_timing_duty": "unresolved",
            "signal_form_judgment": "unresolved", "physical_pixel_visibility": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = measure(case_id=args.case, context_path=args.context,
                     trace_path=args.trace, receipt_path=args.receipt)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
