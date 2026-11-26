"""Independently reopen original speed/posting comparison attempts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis import measure
from speed_delivery import ASSIGNMENT, compare


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempts, comparison, plan):
    plan = json.loads(Path(plan).read_text())
    target = next((row for row in plan["comparisons"]
                   if row["comparison_id"] == comparison), None)
    if target is None or len(attempts) != len(target["case_ids"]):
        raise ValueError("exact speed comparison members missing")
    attempts = [Path(value) for value in attempts]
    measured = [measure(attempt) for attempt in attempts]
    if [row["case_id"] for row in measured] != target["case_ids"]:
        raise ValueError("comparison attempt identities differ")
    fixture = [(attempt / "fixture-provenance.json").is_file() for attempt in attempts]
    if len(set(fixture)) != 1:
        raise ValueError("comparison source profiles differ")
    keys = [case.removeprefix(ASSIGNMENT + "__") for case in target["case_ids"]]
    different = comparison == "different_posted_exception"
    result = compare(measured, keys, varying_posting=different, diagnostic_fixture=fixture[0])
    sites = [json.loads((attempt / "site.json").read_text()) for attempt in attempts]
    if different:
        postings = [site["signs"][0]["value_mph"] for site in sites]
        if postings != [25, 35]:
            raise ValueError("different posted value contrast missing")
        for site in sites:
            site.pop("signs")
        if any(site != sites[0] for site in sites[1:]):
            raise ValueError("posting contrast changed fixed site context")
    elif len({_sha(attempt / "site.json") for attempt in attempts}) != 1:
        raise ValueError("speed sweep changed fixed posting source")
    configs = [json.loads((attempt / "config.json").read_text()) for attempt in attempts]
    for config in configs:
        if config.get("cell_id") != "C150979" or config.get("actor") != "motor_vehicle_driver":
            raise ValueError("comparison changed cell or actor")
    if len({config.get("throttle_scale") for config in configs}) != 1:
        raise ValueError("comparison changed controller candidate")
    return {"format": "c150979-independent-speed-comparison-v1",
            "comparison_id": comparison, "case_ids": result["case_ids"],
            "fixed_conditions": target["fixed_conditions"],
            "deliberate_differences": target["deliberate_differences"],
            "measured": result,
            "source_hashes": {case: {"site": _sha(attempt / "site.json"),
                                     "history": _sha(attempt / "history.json")}
                              for case, attempt in zip(target["case_ids"], attempts)},
            "diagnostic_fixture": fixture[0], "physical_acceptance": False,
            "legal_posting_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.comparison_id != ASSIGNMENT + "__" + args.comparison:
        raise ValueError("exact speed comparison identity differs")
    if args.output.exists():
        raise ValueError("refusing to overwrite independent comparison audit")
    result = audit(args.attempt, args.comparison, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
