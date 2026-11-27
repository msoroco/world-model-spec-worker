"""Independent fixed-condition and original instruction-response comparisons."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from analysis import measure

ASSIGNMENT = "testing__C177249__NRS-484B-560-7b__motor_vehicle_driver"
COMPARISONS = {
    "device_stop_response": ("device_stop_halt", "device_stop_cross"),
    "device_indication": ("device_stop_cross", "device_clear_cross"),
    "clear_response": ("device_clear_cross", "device_clear_halt"),
    "officer_stop_response": ("officer_stop_halt", "officer_stop_cross"),
    "governing_channel": ("device_stop_halt", "officer_stop_halt"),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixed(site):
    value = copy.deepcopy(site)
    value.pop("case", None)
    value.pop("_packet_sha256", None)
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
        raise ValueError("railway comparison fixed original map, crossing, device, officer, vehicle or route differ")
    configs = [json.loads((Path(attempt) / "config.json").read_text()) for attempt in attempts]
    if any((c["duration_s"], c["rate_hz"], c["cameras"]) !=
           (configs[0]["duration_s"], configs[0]["rate_hz"], configs[0]["cameras"])
           for c in configs[1:]):
        raise ValueError("railway comparison fixed camera/duration differ")
    for site, name in zip(sites, COMPARISONS[comparison]):
        if site["case"]["name"] != name:
            raise ValueError("railway comparison source case differs")
    intended = [site["case"] for site in sites]
    response_observed = [(item["observed_halt_before_entry"], item["observed_crossing_entry"])
                         for item in measured]
    for case, response in zip(intended, response_observed):
        if case["response"] == "halt" and response != (True, False):
            raise ValueError("original halt response differs from selected case")
        if case["response"] == "cross" and response != (False, True):
            raise ValueError("original crossing response differs from selected case")
    if comparison in ("device_stop_response", "clear_response", "officer_stop_response"):
        if (intended[0]["authority"], intended[0]["instruction"]) != (intended[1]["authority"], intended[1]["instruction"]) or response_observed[0] == response_observed[1]:
            raise ValueError("original response contrast lacks fixed instruction and measured difference")
    elif comparison == "device_indication":
        if (intended[0]["instruction"], intended[1]["instruction"]) != ("stop", "clear") or response_observed[0] != response_observed[1]:
            raise ValueError("original stop/clear indication contrast differs")
    elif comparison == "governing_channel":
        if (intended[0]["authority"], intended[1]["authority"]) != ("device", "officer") or response_observed[0] != response_observed[1]:
            raise ValueError("original device/officer channel contrast differs")
    return {"format": "c177249-independent-railway-7b-comparison-audit-v1",
            "assignment_id": ASSIGNMENT, "comparison_id": comparison,
            "case_ids": row["case_ids"],
            "site_source_sha256": [sha(Path(attempt) / "site.json") for attempt in attempts],
            "fixed_context_checked": True, "deliberate_difference_checked": True,
            "measured_response": response_observed,
            "diagnostic_fixture": all(item[4] for item in observed),
            "physical_acceptance": False, "instruction_authenticity": "requires independent source review",
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
