"""Source-bound left/right parking observations for NRS 484B.497.

Device permission and legal standing/parking remain unresolved review facts.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C229439__NRS-484B-497__vehicle_parker"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def vector(value):
    if not isinstance(value, list) or len(value) != 2 or any(
            not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
        raise ValueError("finite original two-dimensional vector required")
    return value


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
    for key in ("roadway_public_use_source", "roadway_boundary_source", "marked_lanes_source",
                "direction_restriction_source", "device_inventory_source", "device_erection_source",
                "device_official_status_source", "device_instruction_source", "device_governed_space_source",
                "parking_person_source", "halt_purpose_source"):
        if not context.get(key):
            raise ValueError("original context source missing: " + key)
    origin, forward = vector(context.get("road_origin_xy")), vector(context.get("road_forward_xy"))
    if abs(math.hypot(*forward) - 1) > .02:
        raise ValueError("road forward must be unit length")
    lane_count = context.get("marked_lane_count")
    if not isinstance(lane_count, int) or lane_count < 1:
        raise ValueError("original marked lane inventory required")
    if context.get("one_way_restriction") not in (True, False):
        raise ValueError("original one-way restriction required")
    if context.get("device_kind") not in {"none", "official_park_permit", "official_stand_permit",
                                           "official_restrict", "unofficial_park_permit"}:
        raise ValueError("original device inventory kind required")
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or len(rows) != receipt.get("frame_count") or receipt.get("fps") != 20:
        raise ValueError("original 20 Hz frame count mismatch")
    observations = []
    for index, row in enumerate(rows):
        if row.get("frame") != index or not isinstance(row.get("time_s"), (int, float)) or abs(row["time_s"] - index / 20) > .002:
            raise ValueError("original frame cadence mismatch")
        vertices = row.get("vehicle_vertices")
        if not isinstance(vertices, list) or len(vertices) != 8:
            raise ValueError("eight original vehicle body vertices required")
        lateral = []
        for vertex in vertices:
            if not isinstance(vertex, list) or len(vertex) != 3 or any(
                    not isinstance(x, (int, float)) or not math.isfinite(x) for x in vertex):
                raise ValueError("finite original body vertex required")
            dx, dy = vertex[0] - origin[0], vertex[1] - origin[1]
            lateral.append(forward[0] * dy - forward[1] * dx)
        speed = row.get("speed_mps")
        if not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
            raise ValueError("original speed required")
        if row.get("control_state") not in {"approach", "stop", "stand", "park", "depart"}:
            raise ValueError("original activity control state required")
        observations.append({"frame": index, "time_s": row["time_s"], "leftward_min_m": min(lateral),
                             "leftward_max_m": max(lateral), "speed_mps": speed,
                             "control_state": row["control_state"]})
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": sha(context_path), "trace_sha256": sha(trace_path),
                                "receipt_sha256": sha(receipt_path), "native_map_sha256": context["map_sha256"]},
            "marked_lane_count": lane_count, "one_way_restriction": context["one_way_restriction"],
            "device_kind_source_label": context["device_kind"], "observations": observations,
            "roadway_side_judgment": "unresolved", "device_permission_judgment": "unresolved",
            "activity_judgment": "unresolved", "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "context", "trace", "receipt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = measure(args.case, args.context, args.trace, args.receipt)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
