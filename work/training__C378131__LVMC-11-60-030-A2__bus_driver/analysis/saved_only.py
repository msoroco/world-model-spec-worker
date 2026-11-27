"""Recorded-only bus event extraction from a sealed source inventory.

This path never invokes CARLA. Requests and proximity are retained separately
from observed door, passenger transfer, emergency and designation authority.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from independent_audits import audit_source


def _center(body):
    vertices = body.get("body_vertices_m")
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("participant body geometry missing")
    return [(min(point[axis] for point in vertices) +
             max(point[axis] for point in vertices)) / 2 for axis in (0, 1)]


def extract(attempt, output, *, fixture=False):
    attempt = Path(attempt).resolve()
    output = Path(output)
    if output.exists():
        raise ValueError("retain prior saved measurement output")
    context_path = attempt / "bus_context.json"
    if not context_path.is_file():
        raise ValueError("Missing required source: bus_context.json")
    context = json.loads(context_path.read_text())
    source_receipt = audit_source(attempt, context, fixture=fixture)
    motion_path = attempt / context["source_files"]["motion"]
    motion = [json.loads(line) for line in motion_path.read_text().splitlines() if line.strip()]
    buses = [json.loads(line) for line in
             (attempt / context["source_files"]["bus_body"]).read_text().splitlines() if line.strip()]
    passengers = [json.loads(line) for line in
                  (attempt / context["source_files"]["passenger_body"]).read_text().splitlines() if line.strip()]
    stopped = [row for row in motion if row["bus_speed_mps"] <= .1]
    door_requested = [row for row in stopped if row.get("door_open_request_active") is True]
    if not door_requested:
        raise ValueError("no stopped door-request interval")
    if any(row.get("actual_door_state_observed") is not False for row in motion):
        raise ValueError("unreviewed door state must remain unknown")
    if any(row.get("actual_passenger_transfer_observed") is not False for row in motion):
        raise ValueError("unreviewed passenger transfer must remain unknown")
    if context.get("designation_authority_confirmed") is not False:
        raise ValueError("authored designation cannot establish authority")
    in_zone = 0
    near_door = 0
    for row, bus, passenger in zip(motion, buses, passengers):
        if row["bus_speed_mps"] > .1:
            continue
        x, y = _center(bus)
        if -25 <= x <= -1 and -4 <= y <= 1:
            in_zone += 1
        px, py = _center(passenger)
        if math.hypot(px - x, py - y) <= 4:
            near_door += 1
    if in_zone == 0:
        raise ValueError("no original bus body in authored loading segment")
    if near_door == 0:
        raise ValueError("no original passenger body near stopped bus")
    payload = {
        "format": "worker-saved-bus-loading-measurement",
        "source_kind": context["source_kind"],
        "source_audit_sha256": hashlib.sha256(json.dumps(source_receipt, sort_keys=True).encode()).hexdigest(),
        "source_files_sha256": source_receipt["source_sha256"],
        "zone_kind_requested": context["zone_kind_requested"],
        "route_id_requested": context["route_id_requested"],
        "vehicle_class_requested": context["vehicle_class_requested"],
        "emergency_requested": context["emergency_requested"],
        "stopped_frames_measured": len(stopped),
        "stopped_door_request_frames_measured": len(door_requested),
        "stopped_body_in_authored_segment_frames_measured": in_zone,
        "passenger_near_stopped_bus_frames_measured": near_door,
        "actual_door_state": "unknown_pending_original_pixel_review",
        "actual_passenger_transfer": "unknown_pending_original_pixel_review",
        "designation_authority": "unknown_pending_original_source_review",
        "emergency_facts": "unknown_pending_independent_original_review",
        "physical_completion": "unverified",
        "legal_outcome": "unresolved",
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(extract(args.attempt, args.output, fixture=args.fixture), sort_keys=True))
