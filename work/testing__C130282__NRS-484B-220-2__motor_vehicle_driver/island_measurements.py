"""Original-source rotary-island passage measurements for NRS 484B.220(2).

The side sign is geometric: positive means the island is left of the vehicle's
observed heading, so the vehicle is locally right of it. Samples do not prove
continuous motion between frames or a legal judgment.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C130282__NRS-484B-220-2__motor_vehicle_driver"
SUFFIXES = ("inner_right", "inner_left", "outer_right", "outer_left")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _point(p):
    if not isinstance(p, list) or len(p) != 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in p):
        raise ValueError("finite two-dimensional point required")
    return tuple(p)


def _polygon(p):
    if not isinstance(p, list) or len(p) < 3:
        raise ValueError("source-backed polygon required")
    return [_point(v) for v in p]


def _inside(point, polygon):
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            if x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                inside = not inside
    return inside


def _nearest_on_segment(point, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    length2 = vx * vx + vy * vy
    if length2 <= 0:
        raise ValueError("island polygon has duplicate edge")
    t = min(1, max(0, ((point[0] - a[0]) * vx + (point[1] - a[1]) * vy) / length2))
    return (a[0] + t * vx, a[1] + t * vy)


def _nearest_boundary(point, polygon):
    candidates = [_nearest_on_segment(point, a, b) for a, b in zip(polygon, polygon[1:] + polygon[:1])]
    return min(candidates, key=lambda p: math.dist(point, p))


def _hull(points):
    points = sorted(set(points))
    if len(points) < 3:
        raise ValueError("body footprint has fewer than three corners")
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _segments_intersect(a, b, c, d):
    def cross(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    x1, x2, y1, y2 = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
    if x1 == x2 == y1 == y2 == 0:
        return (max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0])) and
                max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1])))
    return x1 * x2 <= 0 and y1 * y2 <= 0


def _overlap(a, b):
    if any(_inside(p, b) for p in a) or any(_inside(p, a) for p in b):
        return True
    return any(_segments_intersect(x, y, u, v)
               for x, y in zip(a, a[1:] + a[:1]) for u, v in zip(b, b[1:] + b[:1]))


def validate_map(packet, case_id):
    if packet.get("case_id") != case_id or packet.get("layout") != "multilane_roundabout":
        raise ValueError("exact multilane roundabout map identity required")
    if not isinstance(packet.get("native_map_sha256"), str) or len(packet["native_map_sha256"]) != 64:
        raise ValueError("original Native map hash required")
    island = packet.get("island")
    if not isinstance(island, dict) or island.get("kind") != "rotary_traffic_island" or not island.get("identity_source"):
        raise ValueError("source-reviewed rotary traffic island identity required")
    island_polygon = _polygon(island.get("physical_polygon"))
    circulation = _polygon(packet.get("circulation_surface_polygon"))
    lanes = packet.get("circulation_lanes")
    if not isinstance(lanes, list) or len(lanes) < 2 or {lane.get("role") for lane in lanes} != {"inner", "outer"}:
        raise ValueError("connected inner and outer circulation lanes required")
    if any(not lane.get("lane_id") or not lane.get("source_ref") or not lane.get("route_source") for lane in lanes):
        raise ValueError("source-backed circulation lane route required")
    if len({lane["lane_id"] for lane in lanes}) != 2:
        raise ValueError("distinct circulation lane IDs required")
    if not packet.get("connected_route_source") or not packet.get("vehicle_driver_source"):
        raise ValueError("connected route and motor-vehicle driver sources required")
    return island_polygon, circulation, {lane["lane_id"]: lane["role"] for lane in lanes}


def measure(*, case_id, map_path, trace_path, receipt_path):
    if case_id not in {ASSIGNMENT_ID + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact case ID")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("source receipt identity mismatch")
    if receipt.get("diagnostic_fixture"):
        raise ValueError("diagnostic fixture is not delivery evidence")
    if _sha(map_path) != receipt.get("map_sha256") or _sha(trace_path) != receipt.get("trace_sha256"):
        raise ValueError("original source bytes changed")
    packet = json.loads(Path(map_path).read_text(encoding="utf-8"))
    island, circulation, lanes = validate_map(packet, case_id)
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
        center, heading = _point(row.get("ego_center")), _point(row.get("ego_heading"))
        if abs(math.hypot(*heading) - 1) > .02:
            raise ValueError("original ego heading must be unit length")
        if row.get("ego_lane_id") not in lanes:
            raise ValueError("original circulation lane identity missing")
        vertices = row.get("ego_vertices")
        if not isinstance(vertices, list) or len(vertices) != 8:
            raise ValueError("eight original world-space body vertices required")
        footprint_points = []
        for vertex in vertices:
            if not isinstance(vertex, list) or len(vertex) != 3 or not isinstance(vertex[2], (int, float)) or not math.isfinite(vertex[2]):
                raise ValueError("finite original world-space body vertex required")
            footprint_points.append(_point(vertex[:2]))
        footprint = _hull(footprint_points)
        in_passage = _inside(center, circulation)
        nearest = _nearest_boundary(center, island)
        side = heading[0] * (nearest[1] - center[1]) - heading[1] * (nearest[0] - center[0])
        observations.append({"frame": frame, "time_s": time_s,
                             "ego_lane_id": row["ego_lane_id"], "lane_role": lanes[row["ego_lane_id"]],
                             "in_circulation_surface": in_passage,
                             "island_left_of_heading_cross_m": side,
                             "body_overlaps_island": _overlap(footprint, island),
                             "nearest_island_boundary_distance_m": math.dist(center, nearest)})
    passage = [r for r in observations if r["in_circulation_surface"]]
    if not passage:
        raise ValueError("no sampled rotary-island passage")
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"map_packet_sha256": _sha(map_path),
                                "trace_sha256": _sha(trace_path),
                                "receipt_sha256": _sha(receipt_path),
                                "native_map_sha256": packet["native_map_sha256"]},
            "passage_frames": [r["frame"] for r in passage],
            "sampled_right_of_island_frames": [r["frame"] for r in passage if r["island_left_of_heading_cross_m"] > 0 and not r["body_overlaps_island"]],
            "sampled_left_or_overlap_frames": [r["frame"] for r in passage if r["island_left_of_heading_cross_m"] <= 0 or r["body_overlaps_island"]],
            "observations": observations, "continuous_between_frames": "unverified",
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--map", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = measure(case_id=args.case, map_path=args.map, trace_path=args.trace, receipt_path=args.receipt)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
