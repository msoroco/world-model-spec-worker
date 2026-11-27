"""Independent fixed-source audit of exact School-Xing controlled contrasts."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from analysis import measure
import school_crossing as school


VARIABLES = {
    "hold_vs_enter": ("entry_requested",),
    "attempt_vs_presence": ("person_attempt",),
    "approach_vs_opposite_side": ("person_side",),
    "sign_below_100": ("sign_distance",),
    "sign_above_100": ("sign_distance",),
    "display_vs_no_display": ("sign_displayed",),
    "paint_vs_buttons": ("crossing_marking", "sign_placement"),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixed_site(site, differences):
    value = copy.deepcopy(site)
    if "sign_distance" in differences:
        value["sign"].pop("advance_distance_ft")
        value["source_records"].pop("sign_installation")
    if "sign_displayed" in differences:
        value["sign"].pop("displayed")
        value["source_records"].pop("sign_installation")
    if "sign_placement" in differences:
        value["sign"].pop("placement")
        value["source_records"].pop("sign_installation")
    if "crossing_marking" in differences:
        value.pop("crossing_marking")
        value["source_records"].pop("crossing_geometry")
    if "person_attempt" in differences:
        value["person"].pop("attempt_requested")
        value["source_records"].pop("pedestrian_source")
    if "person_side" in differences:
        value["person"].pop("side_relative_to_approach")
        value["source_records"].pop("pedestrian_source")
    return value


def audit(attempts, comparison, comparison_id, plan):
    planned = json.loads(Path(plan).read_text())
    row = next((item for item in planned["comparisons"]
                if item["comparison_id"] == comparison), None)
    if row is None or comparison_id != school.ASSIGNMENT + "__" + comparison:
        raise ValueError("exact School-Xing comparison identity mismatch")
    if comparison not in VARIABLES or len(attempts) != len(row["case_ids"]):
        raise ValueError("School-Xing comparison members differ")
    observed = [measure(attempt) for attempt in attempts]
    if [item[0] for item in observed] != row["case_ids"]:
        raise ValueError("School-Xing member order/identity differs")
    sites = [item[3] for item in observed]
    measured = [item[1] for item in observed]
    cases = [next(c for c in school.CASES if school.ASSIGNMENT + "__" + c.name == case_id)
             for case_id in row["case_ids"]]
    differences = VARIABLES[comparison]
    base = fixed_site(sites[0], differences)
    if any(fixed_site(site, differences) != base for site in sites[1:]):
        raise ValueError("School-Xing comparison fixed original context differs")
    for site, item, case in zip(sites, measured, cases):
        if (site["sign"]["advance_distance_ft"] != case.sign_distance_ft or
                site["sign"]["displayed"] is not case.sign_displayed or
                site["crossing_marking"] != case.crossing_marking or
                site["sign"]["placement"] != case.sign_placement or
                site["person"]["side_relative_to_approach"] != case.person_side or
                site["person"]["attempt_requested"] is not case.person_attempt):
            raise ValueError("School-Xing declared difference differs from source")
        if item["legal_approaching_side_unresolved"] is not True:
            raise ValueError("comparison inserted legal approaching-side judgment")
    if "entry_requested" in differences:
        if measured[0]["entry"] is not None or measured[1]["entry"] is None:
            raise ValueError("hold/entry comparison physical measurement differs")
    if "person_attempt" in differences:
        if [x["entry"]["person_attempt_observed"] for x in measured] != [True, False]:
            raise ValueError("attempt/presence comparison original action differs")
    if "person_side" in differences:
        if [x["entry"]["person_side_relative_to_approach"] for x in measured] != ["approach_side", "opposite_side"]:
            raise ValueError("person side comparison original geometry differs")
    if "sign_distance" in differences:
        expected = [100., 99. if comparison == "sign_below_100" else 101.]
        if [x["sign_advance_distance_ft_measured"] for x in measured] != expected:
            raise ValueError("sign-distance comparison original placement differs")
    if "sign_displayed" in differences:
        if [x["entry"]["frame"] is not None for x in measured] != [True, True] or \
                [x["sign_displayed_at_entry"] for x in measured] != [True, False]:
            raise ValueError("sign-display comparison original state differs")
    return {"format": "c422976-independent-school-crossing-comparison-audit-v1",
            "assignment_id": school.ASSIGNMENT, "comparison_id": comparison,
            "case_ids": row["case_ids"],
            "site_source_sha256": [sha(Path(attempt) / "site.json") for attempt in attempts],
            "observed_entry_frames": [x["entry"]["frame"] if x["entry"] else None
                                      for x in measured],
            "fixed_context_checked": True, "deliberate_difference_checked": True,
            "diagnostic_fixture": all(item[4] for item in observed),
            "physical_acceptance": False, "legal_judgment": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite independent comparison audit")
    value = audit(args.attempt, args.comparison, args.comparison_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
