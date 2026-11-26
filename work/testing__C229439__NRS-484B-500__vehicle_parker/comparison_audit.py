"""Independent source-bound checks for the three planned parking comparisons.

This checks measurement isolation and missing evidence. It does not decide the
legal characterization of a device, place, or person's conduct.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parking_place import ASSIGNMENT


CASES = {
    "park_inside_hazard": ("park", "inside", "hazardous"),
    "park_outside_hazard": ("park", "outside", "hazardous"),
    "stand_inside_hazard": ("stand", "inside", "hazardous"),
    "stop_inside_hazard": ("stop", "inside", "hazardous"),
    "park_inside_congested": ("park", "inside", "congested"),
}
COMPARISONS = {
    "inside_vs_outside": ("park_inside_hazard", "park_outside_hazard"),
    "stop_stand_park": ("park_inside_hazard", "stand_inside_hazard", "stop_inside_hazard"),
    "hazard_vs_congestion": ("park_inside_hazard", "park_inside_congested"),
}


def _load(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(data), {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}


def audit(comparison_id: str, source_paths: dict[str, str | Path]) -> dict:
    if comparison_id not in COMPARISONS:
        raise ValueError("unknown exact comparison")
    names = COMPARISONS[comparison_id]
    if set(source_paths) != set(names):
        raise ValueError("missing or extra exact comparison evidence")
    rows = {}
    for name in names:
        packet, source = _load(source_paths[name])
        conduct, footprint, context = CASES[name]
        if (packet.get("assignment_id") != ASSIGNMENT
                or packet.get("case_id") != ASSIGNMENT + "__" + name
                or packet.get("requested_conduct") != conduct
                or packet.get("requested_footprint") != footprint
                or packet.get("place_context_for_review") != context):
            raise ValueError("case identity or planned contrast differs")
        construction = packet.get("construction")
        measurement = packet.get("measurement")
        if not isinstance(construction, dict) or not isinstance(measurement, dict):
            raise ValueError("original construction and measurement required")
        if (construction.get("assignment_id") != ASSIGNMENT
                or measurement.get("assignment_id") != ASSIGNMENT
                or construction.get("device_id") != measurement.get("device_id")
                or construction.get("designated_place_id") != measurement.get("designated_place_id")):
            raise ValueError("construction and measurement source identity differs")
        observations = measurement.get("observations")
        if not isinstance(observations, list) or len(observations) < 3:
            raise ValueError("original measured footprint history required")
        if not all("body_wholly_within_place" in o and "body_wholly_outside_place" in o
                   and "speed_mps" in o for o in observations):
            raise ValueError("original body and halt observations missing")
        stationary = [o for o in observations if o["speed_mps"] <= 0.1]
        if not stationary:
            raise ValueError("no measured stationary episode")
        if footprint == "inside" and not any(o["body_wholly_within_place"] for o in stationary):
            raise ValueError("inside body footprint absent during halt")
        if footprint == "outside" and not any(o["body_wholly_outside_place"] for o in stationary):
            raise ValueError("outside body footprint absent during halt")
        for field in ("official_authority_source", "loading_activity_source",
                      "officer_or_device_direction_source", "original_trace_id"):
            if not measurement.get(field):
                raise ValueError("missing original context source: " + field)
        rows[name] = {"packet": packet, "source": source}

    def values(field):
        return [rows[name]["packet"][field] for name in names]

    for field in ("vehicle_blueprint", "device_id", "designated_place_id",
                  "camera_plan_sha256", "duration_s", "rate_hz"):
        if any(not row["packet"].get(field) for row in rows.values()) or len(set(values(field))) != 1:
            raise ValueError("fixed comparison condition differs: " + field)
    if comparison_id == "inside_vs_outside":
        for field in ("requested_conduct", "place_context_for_review", "conduct_source_sha256",
                      "place_context_source_sha256"):
            if len(set(values(field))) != 1:
                raise ValueError("fixed comparison condition differs: " + field)
    elif comparison_id == "stop_stand_park":
        for field in ("requested_footprint", "place_context_for_review",
                      "place_context_source_sha256", "parking_pose_sha256"):
            if len(set(values(field))) != 1:
                raise ValueError("fixed comparison condition differs: " + field)
        if len(set(values("conduct_source_sha256"))) != len(names):
            raise ValueError("separate conduct sources required")
    else:
        for field in ("requested_footprint", "requested_conduct", "parking_pose_sha256",
                      "conduct_source_sha256"):
            if len(set(values(field))) != 1:
                raise ValueError("fixed comparison condition differs: " + field)
        if len(set(values("place_context_source_sha256"))) != len(names):
            raise ValueError("separate place-context sources required")
    return {"format": "worker-comparison-audit", "assignment_id": ASSIGNMENT,
            "comparison_id": comparison_id, "passed": True,
            "inputs": {name: rows[name]["source"] for name in names},
            "limit": "Measured isolation only; official status, place character, conduct and actual pixels require independent review."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", choices=COMPARISONS, required=True)
    parser.add_argument("--input", action="append", nargs=2, metavar=("CASE_SUFFIX", "PACKET"), required=True)
    args = parser.parse_args(argv)
    paths = dict(args.input)
    if len(paths) != len(args.input):
        raise ValueError("duplicate exact comparison evidence")
    print(json.dumps(audit(args.comparison, paths), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
