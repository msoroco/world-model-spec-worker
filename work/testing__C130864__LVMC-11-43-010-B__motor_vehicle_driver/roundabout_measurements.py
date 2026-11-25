"""Saved Native geometry and motion audit for LVMC 11.43.010(B).

The outputs are physical observations. No distance or time in this module is a
legal definition of a traffic gap or a right-of-way judgment.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C130864__LVMC-11-43-010-B__motor_vehicle_driver"
SUFFIXES = ("connected_wait", "connected_enter", "adjacent_wait", "adjacent_enter",
            "connected_gap_wait", "connected_gap_enter")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _point(p):
    if not isinstance(p, list) or len(p) != 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in p):
        raise ValueError("finite two-dimensional point required")
    return p


def _polygon(p):
    if not isinstance(p, list) or len(p) < 3:
        raise ValueError("source-backed polygon required")
    return [_point(v) for v in p]


def _inside(point, polygon):
    x, y = point
    result = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            x_at_y = (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]
            if x < x_at_y:
                result = not result
    return result


def validate_map(packet):
    if packet.get("layout") != "multilane_roundabout" or not packet.get("map_sha256") or len(packet["map_sha256"]) != 64:
        raise ValueError("source-hashed multilane roundabout map required")
    if not packet.get("jurisdiction_source") or not packet.get("roundabout_geometry_source"):
        raise ValueError("jurisdiction and original roundabout geometry sources required")
    ring = _polygon(packet.get("circulating_surface_polygon"))
    conflict = _polygon(packet.get("entry_conflict_polygon"))
    lanes = packet.get("circulating_lanes")
    if not isinstance(lanes, list) or len(lanes) < 2 or len({lane.get("lane_id") for lane in lanes}) != len(lanes):
        raise ValueError("two distinct circulating lanes required")
    entry = packet.get("ego_entry_lane")
    if not isinstance(entry, dict) or not entry.get("lane_id") or not entry.get("connected_circulating_lane_id"):
        raise ValueError("ego entry and connected circulating lane required")
    if entry["connected_circulating_lane_id"] not in {lane["lane_id"] for lane in lanes}:
        raise ValueError("ego entry lane is not connected to an inventoried circulating lane")
    other = packet.get("opponent_route")
    if not isinstance(other, dict) or other.get("circulating_lane_id") not in {lane["lane_id"] for lane in lanes}:
        raise ValueError("opponent actual circulating lane and route required")
    if not other.get("route_source") or not other.get("potential_conflict_source"):
        raise ValueError("opponent route/conflict source required")
    if not _inside(_point(other.get("initial_position")), ring):
        raise ValueError("opponent must start inside roundabout")
    line = packet.get("entry_line")
    if not isinstance(line, list) or len(line) != 2 or _point(line[0]) == _point(line[1]):
        raise ValueError("physical entry line required")
    return ring, conflict


def _body(vertices):
    if not isinstance(vertices, list) or len(vertices) != 8:
        raise ValueError("eight original world-space body vertices required")
    result = []
    for vertex in vertices:
        if not isinstance(vertex, list) or len(vertex) != 3 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in vertex):
            raise ValueError("finite three-dimensional body vertex required")
        result.append(vertex[:2])
    return result


def _minimum_distance(a, b):
    return min(math.dist(x, y) for x in a for y in b)


def measure(*, case_id, map_path, trace_path, receipt_path,
            allow_diagnostic=False):
    if case_id not in {ASSIGNMENT_ID + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact case ID")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("source receipt identity mismatch")
    if receipt.get("diagnostic_fixture") and not allow_diagnostic:
        raise ValueError("diagnostic fixture is not delivery evidence")
    if _sha(map_path) != receipt.get("map_sha256") or _sha(trace_path) != receipt.get("trace_sha256"):
        raise ValueError("original source bytes changed")
    packet = json.loads(Path(map_path).read_text(encoding="utf-8"))
    ring, conflict = validate_map(packet)
    if packet.get("case_id") != case_id:
        raise ValueError("original map case mismatch")
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
        ego, opponent = _body(row.get("ego_vertices")), _body(row.get("opponent_vertices"))
        ego_in_ring = any(_inside(p, ring) for p in ego)
        opponent_in_ring = any(_inside(p, ring) for p in opponent)
        ego_in_conflict = any(_inside(p, conflict) for p in ego)
        opponent_in_conflict = any(_inside(p, conflict) for p in opponent)
        for key in ("ego_speed_mps", "opponent_speed_mps"):
            if not isinstance(row.get(key), (int, float)) or not math.isfinite(row[key]) or row[key] < 0:
                raise ValueError("original vehicle speed missing")
        observations.append({"frame": frame, "time_s": time_s,
                             "ego_in_ring": ego_in_ring, "opponent_in_ring": opponent_in_ring,
                             "ego_in_conflict": ego_in_conflict, "opponent_in_conflict": opponent_in_conflict,
                             "body_vertex_separation_m": _minimum_distance(ego, opponent),
                             "ego_speed_mps": row["ego_speed_mps"],
                             "opponent_speed_mps": row["opponent_speed_mps"]})
    first_entry = next((r for previous_row, r in zip(observations, observations[1:])
                        if not previous_row["ego_in_ring"] and r["ego_in_ring"]), None)
    before_entry = [r for r in observations if first_entry is None or r["frame"] < first_entry["frame"]]
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"map_packet_sha256": _sha(map_path),
                                "original_trace_sha256": _sha(trace_path),
                                "receipt_sha256": _sha(receipt_path),
                                "native_map_sha256": packet["map_sha256"]},
            "ego_entry_lane_id": packet["ego_entry_lane"]["lane_id"],
            "connected_circulating_lane_id": packet["ego_entry_lane"]["connected_circulating_lane_id"],
            "opponent_circulating_lane_id": packet["opponent_route"]["circulating_lane_id"],
            "first_observed_ego_entry_frame": first_entry["frame"] if first_entry else None,
            "opponent_in_ring_at_ego_entry": first_entry["opponent_in_ring"] if first_entry else None,
            "opponent_in_conflict_at_ego_entry": first_entry["opponent_in_conflict"] if first_entry else None,
            "ego_stopped_before_entry_frames": [r["frame"] for r in before_entry if r["ego_speed_mps"] <= .1],
            "body_separation_at_entry_m": first_entry["body_vertex_separation_m"] if first_entry else None,
            "minimum_sampled_body_separation_m": min(r["body_vertex_separation_m"] for r in observations),
            "observations": observations, "legal_gap_judgment": "unresolved",
            "physical_acceptance": "unverified",
            "diagnostic_fixture": bool(receipt.get("diagnostic_fixture"))}


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
