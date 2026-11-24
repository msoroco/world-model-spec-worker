"""Source-bound lane-relative vehicle geometry for NRS 484B.493."""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C412262__NRS-484B-493__motor_vehicle_driver"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(raw):
    if not isinstance(raw, list) or len(raw) != 2 or any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) for x in raw):
        raise ValueError("finite original XY point required")
    return tuple(float(x) for x in raw)


def polyline(raw):
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError("original direction centerline required")
    points = [point(x) for x in raw]
    if any(a == b for a, b in zip(points, points[1:])):
        raise ValueError("nonzero centerline segments required")
    return points


def signed_offset(p, route):
    candidates = []
    for i, (a, b) in enumerate(zip(route, route[1:])):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length2 = dx * dx + dy * dy
        t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
        projection = (a[0] + t * dx, a[1] + t * dy)
        distance = math.dist(p, projection)
        cross = dx * (p[1] - a[1]) - dy * (p[0] - a[0])
        candidates.append((distance, i, cross / math.sqrt(length2)))
    _, segment, offset = min(candidates)
    return {"route_segment_index": segment, "signed_left_offset_m": offset}


def observe(case_id, context_path, trace_path, receipt_path):
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact case identity required")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if receipt.get("source_kind") != "original_native_capture" or receipt.get("diagnostic_fixture"):
        raise ValueError("original Native capture required")
    if (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("source receipt identity mismatch")
    if receipt.get("context_sha256") != digest(context_path) or receipt.get("trace_sha256") != digest(trace_path):
        raise ValueError("original source bytes changed")
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    if context.get("case_id") != case_id:
        raise ValueError("context case identity mismatch")
    for key in ("street_legal_status_source", "street_boundary_source", "public_access_source",
                "city_limits_source", "one_way_order_source", "permitted_direction_source",
                "centerline_source", "notice_erection_source", "notice_authority_source",
                "notice_exact_content_source", "notice_conformity_source", "notice_extent_source",
                "person_identity_source", "vehicle_identity_source", "halt_purpose_source",
                "service_activity_source", "occupancy_source"):
        if not context.get(key):
            raise ValueError("original context source missing: " + key)
    if context.get("one_way_status") not in {"one_way", "two_way", "unresolved"}:
        raise ValueError("source-backed one-way status required")
    if context.get("notice_state") not in {"erected_applicable", "absent", "outside_extent", "unresolved"}:
        raise ValueError("source-backed notice state required")
    route = polyline(context.get("permitted_direction_centerline_xy_m"))
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or receipt.get("fps") != 20 or receipt.get("frame_count") != len(rows):
        raise ValueError("original 20 Hz frame count required")
    samples = []
    for i, row in enumerate(rows):
        if row.get("frame") != i or isinstance(row.get("time_s"), bool) or not isinstance(row.get("time_s"), (int, float)) or not math.isfinite(row["time_s"]) or abs(row["time_s"] - i / 20) > .002:
            raise ValueError("original frame cadence mismatch")
        center = point(row.get("vehicle_center_xy_m"))
        body_raw = row.get("vehicle_body_polygon_xy_m")
        if not isinstance(body_raw, list) or len(body_raw) < 3:
            raise ValueError("original vehicle body polygon required")
        body = [point(x) for x in body_raw]
        speed = row.get("vehicle_speed_mps")
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
            raise ValueError("original nonnegative speed required")
        center_offset = signed_offset(center, route)
        body_offsets = [signed_offset(x, route)["signed_left_offset_m"] for x in body]
        samples.append({"frame": i, "time_s": row["time_s"], "vehicle_speed_mps": speed,
                        "vehicle_center_signed_left_offset_m": center_offset["signed_left_offset_m"],
                        "nearest_route_segment_index": center_offset["route_segment_index"],
                        "body_signed_left_offset_range_m": [min(body_offsets), max(body_offsets)]})
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": digest(context_path), "trace_sha256": digest(trace_path),
                                "receipt_sha256": digest(receipt_path)},
            "one_way_status_source_label": context["one_way_status"],
            "notice_state_source_label": context["notice_state"], "samples": samples,
            "left_hand_side_judgment": "unresolved", "stand_or_park_judgment": "unresolved",
            "notice_legal_applicability_judgment": "unresolved", "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "context", "trace", "receipt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = observe(args.case, args.context, args.trace, args.receipt)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
