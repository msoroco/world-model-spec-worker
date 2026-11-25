"""Independent source-bound comparison audit of two saved exact cases."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit

BASE = "testing__C125714__NRS-484B-203-1__motor_vehicle_driver__right_half"
PAIRS = {
    "direction_relative_right_side": "wrong_side",
    "half_paved_allocation": "left_encroachment",
    "physical_constraint_context": "right_constrained",
}


def check(comparison_id, base_attempt, other_attempt, *, diagnostic=False):
    if comparison_id not in PAIRS:
        raise ValueError("unknown comparison")
    other_case = BASE.rsplit("__", 1)[0] + "__" + PAIRS[comparison_id]
    base, other = Path(base_attempt), Path(other_attempt)
    source_audits = (audit(base, BASE, diagnostic=diagnostic),
                     audit(other, other_case, diagnostic=diagnostic))
    configs = [json.loads((path / "config.json").read_text()) for path in (base, other)]
    maps = [json.loads((path / "reviewed-map.json").read_text()) for path in (base, other)]
    reports = [json.loads((path / "analysis-report.json").read_text()) for path in (base, other)]
    for key in ("actor", "law_id", "duration_s", "cameras"):
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError("fixed capture condition differs: " + key)
    for key in ("public_highway", "encounter_on_undivided_approach",
                "paved_y_bounds_m", "cross_sections", "paved_boundary_source",
                "traffic_line_capacity_each_direction", "capacity_source",
                "opposing_lane_directions", "ego_half_width_m", "other_half_width_m"):
        if maps[0].get(key) != maps[1].get(key):
            raise ValueError("fixed original road condition differs: " + key)
    values = [report["measurements"]["opposing_pass_measurement"]["value"]
              for report in reports]
    if comparison_id == "direction_relative_right_side":
        if values[0]["right_of_other_all"] is not True or values[1]["right_of_other_all"] is not False:
            raise ValueError("declared direction-relative difference absent")
    elif comparison_id == "half_paved_allocation":
        if not values[0]["ego_yielded_paved_fraction_min"] > values[1]["ego_yielded_paved_fraction_min"]:
            raise ValueError("declared paved allocation difference absent")
    else:
        if (maps[1].get("physical_constraint", {}).get("source_id") is None or
                not values[0]["ego_yielded_paved_fraction_min"] >
                values[1]["ego_yielded_paved_fraction_min"]):
            raise ValueError("declared physical constraint difference absent")
    return {"format": "worker-comparison-audit-diagnostic" if diagnostic else "worker-comparison-audit",
            "comparison_id": comparison_id, "case_ids": [BASE, other_case],
            "source_hashes": [item["source_hashes"] for item in source_audits],
            "physical_acceptance_claimed": False if diagnostic else all(
                item["physical_acceptance_claimed"] for item in source_audits),
            "passed": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--base-attempt", required=True)
    parser.add_argument("--other-attempt", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.comparison, args.base_attempt, args.other_attempt,
                           diagnostic=args.diagnostic), sort_keys=True))


if __name__ == "__main__":
    main()
