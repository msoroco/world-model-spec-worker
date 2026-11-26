"""Selected two-attempt source comparison with diagnostic/original separation."""

import argparse
import json
from pathlib import Path

from comparison_audit import audit as audit_original_comparison
from selected_delivery import audit as audit_selected


TIMING = {"entrant_departure_s", "subject_departure_s"}


def _read(attempt, name):
    path = Path(attempt) / name
    if not path.is_file():
        raise ValueError("comparison source missing: " + name)
    return json.loads(path.read_text())


def audit(left, right, left_case, right_case, allow_diagnostic=False,
          left_site_sha256=None, right_site_sha256=None):
    left = Path(left).resolve()
    right = Path(right).resolve()
    if left == right or left_case == right_case:
        raise ValueError("distinct exact comparison sources required")
    left_config = _read(left, "config.json")
    right_config = _read(right, "config.json")
    if left_config.get("selected_case_id") != left_case or \
            right_config.get("selected_case_id") != right_case:
        raise ValueError("comparison case selection mismatch")
    fixed_left = {key: value for key, value in left_config["scenario_parameters"].items()
                  if key not in TIMING}
    fixed_right = {key: value for key, value in right_config["scenario_parameters"].items()
                   if key not in TIMING}
    if fixed_left != fixed_right or left_config["cameras"] != right_config["cameras"] or \
            left_config["frame_count"] != right_config["frame_count"]:
        raise ValueError("fixed zone, actor or camera construction changed")
    if allow_diagnostic:
        left_selected = audit_selected(left, left_case, allow_diagnostic=True)
        right_selected = audit_selected(right, right_case, allow_diagnostic=True)
        if not left_selected["diagnostic_fixture"] or not right_selected["diagnostic_fixture"]:
            raise ValueError("diagnostic comparison mixed original sources")
        left_measurement = _read(left, "analysis-report.json")["measurements"]["restricted_zone_entrant_observations"]["value"]
        right_measurement = _read(right, "analysis-report.json")["measurements"]["restricted_zone_entrant_observations"]["value"]
        return {"case_ids": [left_case, right_case], "fixed_construction_matched": True,
                "source_hashes": [left_selected["source_sha256"], right_selected["source_sha256"]],
                "observed_differences": {key: [left_measurement[key], right_measurement[key]]
                                         for key in ("entrant_waiting_frames", "entrant_access_blocked_frames",
                                                     "passenger_exchange_frames", "subject_zone_dwell_frames")},
                "diagnostic_fixture": True, "physical_acceptance_claimed": False,
                "legal_comparison": "unresolved_judgment"}
    if not left_site_sha256 or not right_site_sha256:
        raise ValueError("independent original comparison source hashes required")
    return audit_original_comparison(left, right, left_case, right_case,
                                     left_site_sha256, right_site_sha256)


def main():
    parser = argparse.ArgumentParser()
    for name in ("left", "right", "left-case", "right-case"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--allow-diagnostic", action="store_true")
    parser.add_argument("--left-site-sha256")
    parser.add_argument("--right-site-sha256")
    args = parser.parse_args()
    print(json.dumps(audit(args.left, args.right, args.left_case, args.right_case,
                           args.allow_diagnostic, args.left_site_sha256,
                           args.right_site_sha256), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
