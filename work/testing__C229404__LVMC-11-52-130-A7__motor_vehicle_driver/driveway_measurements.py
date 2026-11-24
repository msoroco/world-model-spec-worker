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
    if not isinstance(value, list) or len(value) != 2 or any(
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


def measure(case_id, context_path, trace_path, receipt_path):
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
    if not isinstance(context.get("map_sha256"), str) or len(context["map_sha256"]) != 64:
        raise ValueError("source map hash required")
    for key in ("mouth_source", "frontage_source", "driveway_use_source", "responsible_person_source",
                "relationship_source", "purpose_source", "traffic_direction_source", "postal_status_source"):
        if not context.get(key):
            raise ValueError("original context source missing: " + key)
    a, b = point(context.get("mouth_start_xy")), point(context.get("mouth_end_xy"))
    segment_distance(a, a, b)
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
                             "speed_mps": speed, "control_state": row["control_state"]})
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": sha(context_path), "trace_sha256": sha(trace_path),
                                "receipt_sha256": sha(receipt_path), "native_map_sha256": context["map_sha256"]},
            "driveway_kind": context["driveway_kind"], "observations": observations,
            "minimum_observed_vertex_to_mouth_m": min(r["minimum_sampled_vertex_to_mouth_m"] for r in observations),
            "five_feet_m_reference_only": 1.524, "frontage_judgment": "unresolved",
            "activity_judgment": "unresolved", "necessity_judgment": "unresolved",
            "private_relationship_judgment": "unresolved", "postal_exception_judgment": "unresolved",
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
