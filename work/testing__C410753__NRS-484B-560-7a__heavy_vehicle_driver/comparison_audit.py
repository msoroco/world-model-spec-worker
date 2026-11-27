"""Independent fixed-condition and original-measurement railway comparisons."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from analysis import measure

ASSIGNMENT = "testing__C410753__NRS-484B-560-7a__heavy_vehicle_driver"
COMPARISONS = {
    "space_halt_vs_clear": ("space_halt_before_15ft", "space_clear_beyond_15ft"),
    "clearance_ground_vs_pass": ("clearance_grounded_before_15ft", "clearance_pass_beyond_15ft"),
    "cause_space_vs_clearance": ("space_halt_before_15ft", "clearance_grounded_before_15ft"),
    "completion_below_at": ("trailing_end_14_9ft", "trailing_end_15_0ft"),
    "completion_at_above": ("trailing_end_15_0ft", "trailing_end_15_1ft"),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixed(site):
    value = copy.deepcopy(site)
    value.pop("case", None)
    value.pop("_packet_sha256", None)
    value.pop("source_sha256", None)
    # Obstruction/profile readback may vary; common rail geometry and map may not.
    readback = value.get("native_readback", {})
    readback.pop("downstream_space_source_sha256", None)
    readback.pop("undercarriage_source_sha256", None)
    readback.pop("crossing_profile_source_sha256", None)
    return value


def audit(attempts, comparison, comparison_id, plan):
    planned = json.loads(Path(plan).read_text())
    row = next((item for item in planned["comparisons"]
                if item["comparison_id"] == comparison), None)
    if row is None or comparison_id != ASSIGNMENT + "__" + comparison:
        raise ValueError("exact railway comparison identity differs")
    if comparison not in COMPARISONS or len(attempts) != len(row["case_ids"]):
        raise ValueError("railway comparison members differ")
    if row["case_ids"] != [ASSIGNMENT + "__" + name for name in COMPARISONS[comparison]]:
        raise ValueError("railway comparison plan changed")
    observed = [measure(attempt) for attempt in attempts]
    if [item[0] for item in observed] != row["case_ids"]:
        raise ValueError("railway comparison member order/identity differs")
    sites = [item[3] for item in observed]
    measured = [item[1] for item in observed]
    baseline = fixed(sites[0])
    if any(fixed(site) != baseline for site in sites[1:]):
        raise ValueError("railway comparison fixed original map, rails, vehicle or route differ")
    configs = [json.loads((Path(attempt) / "config.json").read_text()) for attempt in attempts]
    if any((c["duration_s"], c["rate_hz"], c["cameras"]) !=
           (configs[0]["duration_s"], configs[0]["rate_hz"], configs[0]["cameras"])
           for c in configs[1:]):
        raise ValueError("railway comparison fixed camera/duration differ")
    for site, name in zip(sites, COMPARISONS[comparison]):
        if site["case"]["name"] != name:
            raise ValueError("railway comparison source case differs")
    if comparison == "space_halt_vs_clear":
        if not (sites[0]["case"]["available_space_m"] < sites[1]["case"]["available_space_m"] and
                measured[0]["halt_before_15ft_observed"] and
                not measured[1]["halt_before_15ft_observed"] and
                measured[0]["space_evidence"]):
            raise ValueError("opposite-side-space contrast lacks physical measurement")
    elif comparison == "clearance_ground_vs_pass":
        if not (sites[0]["case"]["minimum_clearance_m"] < sites[1]["case"]["minimum_clearance_m"] and
                measured[0]["halt_before_15ft_observed"] and
                measured[0]["contact_evidence"] and
                not measured[1]["contact_evidence"]):
            raise ValueError("undercarriage-clearance contrast lacks physical contact")
    elif comparison == "cause_space_vs_clearance":
        if not (measured[0]["space_evidence"] and not measured[0]["contact_evidence"] and
                measured[1]["contact_evidence"] and not measured[1]["space_evidence"] and
                all(x["halt_before_15ft_observed"] for x in measured)):
            raise ValueError("space/clearance causal-source contrast differs")
    else:
        targets = (14.9, 15.) if comparison == "completion_below_at" else (15., 15.1)
        if any(abs(site["case"]["target_trailing_end_ft"] - target) > 1e-9 or
               abs(item["maximum_trailing_end_ft"] - target) > .05
               for site, item, target in zip(sites, measured, targets)):
            raise ValueError("original trailing-end 15-foot boundary contrast differs")
    return {"format": "c410753-independent-railway-7a-comparison-audit-v1",
            "assignment_id": ASSIGNMENT, "comparison_id": comparison,
            "case_ids": row["case_ids"],
            "site_source_sha256": [sha(Path(attempt) / "site.json") for attempt in attempts],
            "fixed_context_checked": True, "deliberate_difference_checked": True,
            "measured_trailing_end_ft": [item["maximum_trailing_end_ft"] for item in measured],
            "diagnostic_fixture": all(item[4] for item in observed),
            "physical_acceptance": False, "causal_attribution": "requires independent source review",
            "legal_judgment": None}


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
    result = audit(args.attempt, args.comparison, args.comparison_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
