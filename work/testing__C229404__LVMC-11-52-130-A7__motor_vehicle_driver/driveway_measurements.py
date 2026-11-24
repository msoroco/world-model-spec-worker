"""Source-bound driveway distance and vehicle activity observations.

These measurements do not decide whether a vehicle is legally in front of a
driveway, whether stopping is necessary, or who qualifies for an exception.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C229404__LVMC-11-52-130-A7__motor_vehicle_driver"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2 or any(
            not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError("finite original two-dimensional point required")
    return value


def segment_distance(p, a, b):
    p, a, b = point(p), point(a), point(b)
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 <= 1e-8:
        raise ValueError("driveway mouth has zero length")
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def cross(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def footprint_hull(vertices):
    """Recover the ground footprint from the eight original body vertices."""
    points = sorted({(v[0], v[1]) for v in vertices})
    if len(points) < 3:
        raise ValueError("original vehicle footprint is degenerate")
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3:
        raise ValueError("original vehicle footprint is degenerate")
    return hull


def footprint_to_mouth_distance(vertices, a, b):
    """Distance between the full convex vehicle footprint and mouth segment."""
    hull = footprint_hull(vertices)
    edges = list(zip(hull, hull[1:] + hull[:1]))
    def inside(p):
        return all(cross(u, v, p) >= -1e-9 for u, v in edges)
    if inside(a) or inside(b):
        return 0.0
    for u, v in edges:
        x1, x2 = cross(a, b, u), cross(a, b, v)
        y1, y2 = cross(u, v, a), cross(u, v, b)
        if x1 * x2 <= 0 and y1 * y2 <= 0:
            return 0.0
    return min([segment_distance(p, a, b) for p in hull]
               + [segment_distance(p, u, v) for p in (a, b) for u, v in edges])


def measure(case_id, context_path, trace_path, receipt_path, map_path):
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact assignment case ID required")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("source receipt identity mismatch")
    if receipt.get("diagnostic_fixture") or receipt.get("source_kind") != "original_native_capture":
        raise ValueError("original Native capture required")
    if receipt.get("context_sha256") != sha(context_path) or receipt.get("trace_sha256") != sha(trace_path):
        raise ValueError("original source bytes changed")
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    if context.get("case_id") != case_id or context.get("driveway_kind") not in {"public", "private"}:
        raise ValueError("exact source driveway context required")
    if context.get("map_sha256") != sha(map_path) or receipt.get("map_sha256") != sha(map_path):
        raise ValueError("original map bytes changed or source map hash missing")
    for key in ("mouth_source", "frontage_source", "driveway_use_source", "responsible_person_source",
                "relationship_source", "purpose_source", "traffic_direction_source", "postal_status_source"):
        if not context.get(key):
            raise ValueError("original context source missing: " + key)
    a, b = point(context.get("mouth_start_xy")), point(context.get("mouth_end_xy"))
    segment_distance(a, a, b)
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or len(rows) != receipt.get("frame_count") or receipt.get("fps") != 20:
        raise ValueError("original 20 Hz frame count mismatch")
    plan = json.loads((Path(__file__).parent / "case-plan.json").read_text(encoding="utf-8"))
    exact_case = next((item for item in plan["cases"] if item["case_id"] == case_id), None)
    if exact_case is None:
        raise ValueError("case absent from exact plan")
    activity = exact_case["activity"]
    observations = []
    for index, row in enumerate(rows):
        if row.get("frame") != index or not isinstance(row.get("time_s"), (int, float)) or abs(row["time_s"] - index / 20) > .002:
            raise ValueError("original frame cadence mismatch")
        vertices = row.get("vehicle_vertices")
        if not isinstance(vertices, list) or len(vertices) != 8:
            raise ValueError("eight original vehicle body vertices required")
        distances = []
        for vertex in vertices:
            if not isinstance(vertex, list) or len(vertex) != 3 or any(
                    not isinstance(v, (int, float)) or not math.isfinite(v) for v in vertex):
                raise ValueError("finite original body vertex required")
            distances.append(segment_distance(vertex[:2], a, b))
        speed = row.get("speed_mps")
        if not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
            raise ValueError("original speed required")
        if row.get("control_state") not in {"approach", "stop", "stand", "park", "depart"}:
            raise ValueError("original activity control state required")
        observations.append({"frame": index, "time_s": row["time_s"],
                             "minimum_sampled_vertex_to_mouth_m": min(distances),
                             "full_footprint_to_mouth_m": footprint_to_mouth_distance(vertices, a, b),
                             "speed_mps": speed, "control_state": row["control_state"]})
    # The approach can cross the mouth before the vehicle reaches its final
    # position. Use only a continuous, settled window for spatial evidence.
    settled = []
    windows = []
    for row in observations:
        if row["control_state"] == activity and row["speed_mps"] <= 0.1:
            settled.append(row)
        else:
            if len(settled) >= 20:
                windows.append(settled)
            settled = []
    if len(settled) >= 20:
        windows.append(settled)
    if not windows:
        raise ValueError("no sustained stationary exact-activity window (20 frames)")
    witness = max(windows, key=lambda rows: (len(rows), -rows[0]["frame"]))
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": sha(context_path), "trace_sha256": sha(trace_path),
                                "receipt_sha256": sha(receipt_path), "native_map_sha256": sha(map_path)},
            "driveway_kind": context["driveway_kind"], "observations": observations,
            "activity_window": {"state": activity, "start_frame": witness[0]["frame"],
                                "end_frame": witness[-1]["frame"], "frame_count": len(witness),
                                "stationary_speed_ceiling_mps": 0.1},
            "minimum_observed_vertex_to_mouth_m": min(r["minimum_sampled_vertex_to_mouth_m"] for r in witness),
            "minimum_observed_full_footprint_to_mouth_m": min(r["full_footprint_to_mouth_m"] for r in witness),
            "maximum_observed_full_footprint_to_mouth_m": max(r["full_footprint_to_mouth_m"] for r in witness),
            "five_feet_m_reference_only": 1.524, "frontage_judgment": "unresolved",
            "activity_judgment": "unresolved", "necessity_judgment": "unresolved",
            "private_relationship_judgment": "unresolved", "postal_exception_judgment": "unresolved",
            "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "context", "trace", "receipt", "map", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = measure(args.case, args.context, args.trace, args.receipt, args.map)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
