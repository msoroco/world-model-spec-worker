"""Independent fixed-condition comparison of original one-way curb attempts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit as audit_delivery, read, require, digest

BASE = "heldout__C152972__NRS-484B-400-5__motor_vehicle_driver__"
PAIRS = {
    "approach_left_curb_position": (BASE + "approach_near_depart_near", BASE + "approach_far_depart_near", "approach", "leaving_intersection"),
    "turn_departure_curb_position": (BASE + "approach_near_depart_near", BASE + "approach_near_depart_far", "leaving_intersection", "approach"),
    "turn_departure_left_curb_position": (BASE + "approach_near_depart_near", BASE + "approach_near_depart_far", "leaving_intersection", "approach"),
}


def audit(comparison, attempts, processed, manifest):
    require(comparison in PAIRS and len(attempts) == len(processed) == 2,
            "Two exact one-way curb attempts required")
    first_id, second_id, varied_phase, held_phase = PAIRS[comparison]
    first = audit_delivery(first_id, attempts[0], processed[0], manifest)
    second = audit_delivery(second_id, attempts[1], processed[1], manifest)
    roots = [Path(path) for path in attempts]
    geometry = [read(root / "oneway_geometry_original.json") for root in roots]
    bodies = [read(root / "body_ground_original.json") for root in roots]
    require(first["source_sha256"]["oneway_geometry_original.json"] == second["source_sha256"]["oneway_geometry_original.json"],
            "Fixed original map and left-curb geometry changed")
    for name in ("intersection_id", "map_source", "source_directionality", "destination_directionality", "maneuver"):
        require(geometry[0].get(name) == geometry[1].get(name), "Fixed one-way geometry changed: " + name)
    require(bodies[0].get("subject_id") == bodies[1].get("subject_id"), "Fixed subject identity changed")
    all_rows = [body["frames"] for body in bodies]
    require(len(all_rows[0]) == len(all_rows[1]) and
            [(row["frame"], row["time_s"], row["phase"]) for row in all_rows[0]] ==
            [(row["frame"], row["time_s"], row["phase"]) for row in all_rows[1]],
            "Fixed original frame and phase schedule changed")
    held = [[row["ground_corners"] for row in rows if row["phase"] == held_phase] for rows in all_rows]
    require(held[0] and held[0] == held[1], "Held original body phase changed")
    varied = [[row["ground_corners"] for row in rows if row["phase"] == varied_phase] for rows in all_rows]
    require(varied[0] and varied[0] != varied[1], "Declared original body difference absent")
    metric = "approach_left_curb_nearest_m" if varied_phase == "approach" else "departure_left_curb_nearest_m"
    fixed_metric = "departure_left_curb_nearest_m" if varied_phase == "approach" else "approach_left_curb_nearest_m"
    require(abs(first[fixed_metric] - second[fixed_metric]) < .001, "Held curb measurement changed")
    require(abs(first[metric] - second[metric]) > .1, "Declared curb measurement did not vary")
    configs = [read(root / "config.json") for root in roots]
    require(configs[0].get("curb_offsets_m") != configs[1].get("curb_offsets_m"), "Controller target difference absent")
    for key in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras"):
        require(configs[0].get(key) == configs[1].get(key), "Fixed capture condition changed: " + key)
    return {"format": "worker-oneway-curb-comparison-audit", "comparison_id": comparison,
            "case_ids": [first_id, second_id], "fixed_original_geometry_sha256": digest(roots[0] / "oneway_geometry_original.json"),
            "fixed_phase": held_phase, "varied_phase": varied_phase,
            "measured_original_curb_m": [first[metric], second[metric]],
            "fixed_original_curb_m": [first[fixed_metric], second[fixed_metric]],
            "comparison_complete": True, "diagnostic_fixture": True,
            "actual_motion_separation_verified": False, "legal_conclusion": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt", action="append", required=True)
    parser.add_argument("--processed", action="append", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(args.comparison, args.attempt, args.processed, args.manifest)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
