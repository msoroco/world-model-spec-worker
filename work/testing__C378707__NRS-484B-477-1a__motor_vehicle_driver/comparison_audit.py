"""Independent command for one source-bound business-alley comparison."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_comparisons import PAIRS, compare
from audit_original_attempt import audit as audit_original
from alley_construction import ASSIGNMENT


def diagnostic_compare(comparison, attempts, members):
    sources = [attempt / "original-attempt" for attempt in attempts]
    measured = []
    sites = []
    for source, member in zip(sources, members):
        finding = audit_original(source, member)
        if finding["diagnostic_fixture"] is not True:
            raise ValueError("mixed diagnostic and Native comparison")
        measured.append(json.loads((source / "activity-measurement.json").read_text()))
        sites.append(json.loads((source / "site.json").read_text()))
    if (sites[0].get("reviewed_sources", {}).get("map") !=
            sites[1].get("reviewed_sources", {}).get("map") or
            sites[0].get("alley_kind") != sites[1].get("alley_kind")):
        raise ValueError("fixed alley/map context differs")
    configs = [json.loads((attempt / "config.json").read_text()) for attempt in attempts]
    if any((cfg["duration_s"], cfg["rate_hz"], cfg["cameras"]) !=
           (configs[0]["duration_s"], configs[0]["rate_hz"], configs[0]["cameras"])
           for cfg in configs[1:]):
        raise ValueError("fixed capture context differs")
    first, second = [m["intervals_s"] for m in measured]
    if not first["halt"] or not second["halt"]:
        raise ValueError("diagnostic original vehicle halt absent")
    if comparison == "passenger_active_vs_waiting":
        valid = bool(first["passenger_contact"] and second["passenger_contact"] and
                     first["passenger_contact"][0][0] < second["passenger_contact"][0][0])
    elif comparison == "passenger_stop_vs_driver_exit":
        valid = not first["driver_outside"] and bool(second["driver_outside"])
    elif comparison == "passenger_vs_goods":
        valid = bool(first["passenger_contact"] and not first["goods_contact"] and
                     second["goods_contact"] and not second["passenger_contact"])
    elif comparison == "goods_active_vs_interrupted":
        valid = len(first["goods_contact"]) == 1 and len(second["goods_contact"]) >= 2
    else:
        valid = (measured[0]["ordinance_applicable_frames"] == 0 and
                 measured[1]["ordinance_applicable_frames"] > 0 and
                 bool(first["passenger_contact"] and second["passenger_contact"]))
    if not valid:
        raise ValueError("diagnostic deliberate activity contrast absent")
    return {"comparison_id": comparison, "case_ids": members,
            "fixed_context_checked": True, "deliberate_difference_checked": True,
            "source_activity_sha256": [item["history_sha256"] for item in measured],
            "diagnostic_fixture": True, "physical_acceptance": False,
            "legal_conclusion": "unreviewed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    row = next((item for item in plan["comparisons"] if item["comparison_id"] == args.comparison), None)
    if row is None or args.comparison_id != ASSIGNMENT + "__" + args.comparison:
        raise ValueError("exact comparison identity differs")
    if args.comparison not in PAIRS or len(args.attempt) != 2:
        raise ValueError("comparison member count differs")
    members = [ASSIGNMENT + "__" + name for name in PAIRS[args.comparison]]
    if row["case_ids"] != members:
        raise ValueError("comparison plan members differ")
    if args.output.exists():
        raise ValueError("refusing to replace independent comparison audit")
    inventory = json.loads((args.attempt[0] / "original-attempt/inventory.json").read_text())
    outcome = (diagnostic_compare(args.comparison, args.attempt, members)
               if inventory.get("diagnostic_fixture") is True else
               compare(args.comparison, *(attempt / "original-attempt" for attempt in args.attempt)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
