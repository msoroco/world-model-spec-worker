"""Source-bound vehicle-body clearance from a marked crosswalk."""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C394507__LVMC-11-52-130-A12__motor_vehicle_driver"
TWENTY_FEET_M = 6.096


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(raw):
    if not isinstance(raw, list) or len(raw) != 2 or any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) for x in raw):
        raise ValueError("finite source geometry point required")
    return tuple(float(x) for x in raw)


def polygon(raw):
    if not isinstance(raw, list) or len(raw) < 3:
        raise ValueError("original polygon requires at least three vertices")
    vertices = [point(p) for p in raw]
    if len(set(vertices)) < 3:
        raise ValueError("nondegenerate original polygon required")
    return vertices


def edges(poly):
    return list(zip(poly, poly[1:] + poly[:1]))


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a, b, p):
    return abs(cross(a, b, p)) < 1e-9 and min(a[0], b[0]) - 1e-9 <= p[0] <= max(a[0], b[0]) + 1e-9 and min(a[1], b[1]) - 1e-9 <= p[1] <= max(a[1], b[1]) + 1e-9


def segments_touch(a, b, c, d):
    x, y, z, w = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
    return ((x > 0 > y or x < 0 < y) and (z > 0 > w or z < 0 < w)
            or on_segment(a, b, c) or on_segment(a, b, d) or on_segment(c, d, a) or on_segment(c, d, b))


def inside(p, poly):
    if any(on_segment(a, b, p) for a, b in edges(poly)):
        return True
    x, y = p
    hits = 0
    for a, b in edges(poly):
        if (a[1] > y) != (b[1] > y) and x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
            hits += 1
    return bool(hits % 2)


def point_segment_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == dy == 0:
        return math.dist(p, a)
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def clearance(body, crosswalk):
    if any(inside(p, crosswalk) for p in body) or any(inside(p, body) for p in crosswalk):
        return 0.0
    if any(segments_touch(a, b, c, d) for a, b in edges(body) for c, d in edges(crosswalk)):
        return 0.0
    return min(
        [point_segment_distance(p, a, b) for p in body for a, b in edges(crosswalk)]
        + [point_segment_distance(p, a, b) for p in crosswalk for a, b in edges(body)])


def measure(case_id, context_path, trace_path, receipt_path):
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
    for field in ("jurisdiction_source", "marked_crosswalk_source", "vehicle_identity_source",
                  "responsible_person_source", "destination_purpose_source", "service_activity_source",
                  "traffic_conflict_source", "law_compliance_source", "officer_direction_source",
                  "traffic_device_direction_source", "crosswalk_extent_source"):
        if not context.get(field):
            raise ValueError("original context source missing: " + field)
    crosswalk = polygon(context.get("marked_crosswalk_polygon_xy_m"))
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or receipt.get("fps") != 20 or receipt.get("frame_count") != len(rows):
        raise ValueError("original 20 Hz trace/frame count required")
    samples = []
    for i, row in enumerate(rows):
        if row.get("frame") != i or isinstance(row.get("time_s"), bool) or not isinstance(row.get("time_s"), (int, float)) or abs(row["time_s"] - i / 20) > .002:
            raise ValueError("original frame cadence mismatch")
        speed = row.get("ego_speed_mps")
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
            raise ValueError("original nonnegative speed required")
        body = polygon(row.get("ego_body_polygon_xy_m"))
        samples.append({"frame": i, "time_s": row["time_s"], "ego_speed_mps": speed,
                        "body_to_marked_crosswalk_clearance_m": clearance(body, crosswalk)})
    closest = min(samples, key=lambda row: row["body_to_marked_crosswalk_clearance_m"])
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": digest(context_path), "trace_sha256": digest(trace_path),
                                "receipt_sha256": digest(receipt_path)},
            "twenty_feet_m_arithmetic_reference": TWENTY_FEET_M,
            "closest_source_geometry_frame": closest["frame"],
            "closest_body_to_marked_crosswalk_clearance_m": closest["body_to_marked_crosswalk_clearance_m"],
            "samples": samples, "stop_stand_park_judgment": "unresolved",
            "legal_measurement_convention": "unresolved", "exception_judgment": "unresolved",
            "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "context", "trace", "receipt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = measure(args.case, args.context, args.trace, args.receipt)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
