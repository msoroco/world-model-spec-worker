"""Source-bound entrance/vehicle geometry for NRS 484B.450(1)(j).

The sampled distances are observations, not a legal measurement convention.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C229925__NRS-484B-450-1j__vehicle_stopping_person"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value):
    if not isinstance(value, list) or len(value) != 2 or any(
            not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
        raise ValueError("finite original two-dimensional point required")
    return value


def distance_to_segment(p, a, b):
    p, a, b = point(p), point(a), point(b)
    dx, dy = b[0] - a[0], b[1] - a[1]
    den = dx * dx + dy * dy
    if den <= 1e-8:
        raise ValueError("fire-station entrance has zero width")
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / den))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def measure(case_id, context_path, trace_path, receipt_path):
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact assignment case required")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("original source receipt identity mismatch")
    if receipt.get("diagnostic_fixture") or receipt.get("source_kind") != "original_native_capture":
        raise ValueError("original Native capture required")
    if receipt.get("context_sha256") != sha(context_path) or receipt.get("trace_sha256") != sha(trace_path):
        raise ValueError("original source bytes changed")
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    if context.get("case_id") != case_id or not isinstance(context.get("map_sha256"), str) or len(context["map_sha256"]) != 64:
        raise ValueError("exact source map context required")
    for key in ("station_identity_source", "entrance_boundary_source", "highway_boundary_source",
                "highway_dedication_source", "public_vehicular_use_source", "entrance_side_source",
                "stopping_person_source", "halt_purpose_source", "traffic_conflict_source",
                "law_direction_source", "police_direction_source", "official_device_direction_source"):
        if not context.get(key):
            raise ValueError("original context source missing: " + key)
    a, b = point(context.get("entrance_start_xy")), point(context.get("entrance_end_xy"))
    origin, forward = point(context.get("road_origin_xy")), point(context.get("road_forward_xy"))
    if abs(math.hypot(*forward) - 1) > .02:
        raise ValueError("road forward must be unit length")
    distance_to_segment(a, a, b)
    entrance_lateral = (forward[0] * (a[1] + b[1] - 2 * origin[1]) -
                        forward[1] * (a[0] + b[0] - 2 * origin[0])) / 2
    if abs(entrance_lateral) < .5:
        raise ValueError("entrance side of highway ambiguous")
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or len(rows) != receipt.get("frame_count") or receipt.get("fps") != 20:
        raise ValueError("original 20 Hz frame count mismatch")
    observations = []
    first_frame = rows[0].get("frame")
    first_time = rows[0].get("time_s")
    if type(first_frame) is not int or not isinstance(first_time, (int, float)) or not math.isfinite(first_time):
        raise ValueError("original first frame and time required")
    for index, row in enumerate(rows):
        if row.get("frame") != first_frame + index or not isinstance(row.get("time_s"), (int, float)) or abs(row["time_s"] - first_time - index / 20) > .005:
            raise ValueError("original frame cadence mismatch")
        vertices = row.get("vehicle_vertices")
        if not isinstance(vertices, list) or len(vertices) != 8:
            raise ValueError("eight original vehicle body vertices required")
        distances, lateral = [], []
        for vertex in vertices:
            if not isinstance(vertex, list) or len(vertex) != 3 or any(
                    not isinstance(x, (int, float)) or not math.isfinite(x) for x in vertex):
                raise ValueError("finite original body vertex required")
            distances.append(distance_to_segment(vertex[:2], a, b))
            dx, dy = vertex[0] - origin[0], vertex[1] - origin[1]
            lateral.append(forward[0] * dy - forward[1] * dx)
        speed = row.get("speed_mps")
        if not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
            raise ValueError("original speed required")
        if row.get("control_state") not in {"approach", "stop", "stand", "park", "depart"}:
            raise ValueError("original halt activity required")
        observations.append({"frame": row["frame"], "time_s": row["time_s"],
                             "minimum_sampled_vertex_to_entrance_m": min(distances),
                             "vehicle_lateral_min_m": min(lateral), "vehicle_lateral_max_m": max(lateral),
                             "speed_mps": speed, "control_state": row["control_state"]})
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": sha(context_path), "trace_sha256": sha(trace_path),
                                "receipt_sha256": sha(receipt_path), "native_map_sha256": context["map_sha256"]},
            "entrance_lateral_m": entrance_lateral, "observations": observations,
            "minimum_observed_vertex_to_entrance_m": min(x["minimum_sampled_vertex_to_entrance_m"] for x in observations),
            "twenty_feet_m_reference_only": 6.096, "seventy_five_feet_m_reference_only": 22.86,
            "opposite_highway_side_judgment": "unresolved", "distance_convention_judgment": "unresolved",
            "necessity_or_direction_judgment": "unresolved", "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "context", "trace", "receipt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = measure(args.case, args.context, args.trace, args.receipt)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
