"""Compare two original source packets against a frozen controlled pair.

The audit checks source and construction isolation. It does not assert that
original pixels establish emitted color, range, or a legal outcome.
"""

import argparse
import json
from pathlib import Path

from source_packet import verify


def audit(plan_path, comparison_id, packet_paths, *, diagnostic_fixture=False):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    comparison = next((row for row in plan["comparisons"]
                       if row.get("comparison_id") == comparison_id), None)
    if comparison is None or len(comparison["case_ids"]) != 2 or len(packet_paths) != 2:
        raise ValueError("exact two-case comparison required")
    cases = {case["case_id"]: case for case in plan["cases"]}
    packets = []
    verified = []
    for expected, path in zip(comparison["case_ids"], packet_paths):
        source = verify(path, diagnostic_fixture=diagnostic_fixture)
        if source["case_id"] != expected:
            raise ValueError("original comparison case identity differs")
        packet = json.loads(Path(path).read_text(encoding="utf-8"))
        scene = packet["scene"]
        for key in ("coverage_request", "illumination_request", "motion_request",
                    "calibrated_lamp_request", "lit_state_request", "timing_request",
                    "discernibility_request_ft"):
            if scene[key] != cases[expected][key]:
                raise ValueError("original comparison request differs: " + key)
        verified.append(source)
        packets.append(packet)
    first, second = (packet["scene"] for packet in packets)
    changed = {key for key in set(first) | set(second) if first.get(key) != second.get(key)}
    allowed = set(comparison["vary_fields"])
    if not changed or not changed <= allowed:
        raise ValueError("comparison has missing or undeclared changed scene fields: " +
                         ",".join(sorted(changed - allowed)))
    fixed_refs = {"map_opendrive", "road_sidewalk_geometry", "discernibility_protocol"}
    if not ("coverage_request" in allowed or "vehicle_blueprint" in allowed):
        fixed_refs.add("vehicle_coverage")
    if "timing_request" not in allowed and "local_datetime" not in allowed:
        fixed_refs.add("astronomical_times")
    if not {"illumination_request", "weather", "discernibility_request_ft"} & allowed:
        fixed_refs.add("light_atmosphere")
    if "calibrated_lamp_request" not in allowed:
        fixed_refs.update(("headlamp_photometry", "tail_lamp_photometry"))
    for name in fixed_refs:
        if verified[0]["source_hashes"][name] != verified[1]["source_hashes"][name]:
            raise ValueError("fixed comparison source changed: " + name)
    return {"format": "worker-comparison-source-audit", "comparison_id": comparison_id,
            "case_ids": comparison["case_ids"], "declared_changed_fields": sorted(allowed),
            "observed_changed_fields": sorted(changed), "fixed_source_hashes": {
                name: verified[0]["source_hashes"][name] for name in sorted(fixed_refs)},
            "diagnostic_fixture": diagnostic_fixture, "physical_acceptance": "unverified",
            "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--packet-0", required=True)
    parser.add_argument("--packet-1", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    result = audit(args.plan, args.comparison, [args.packet_0, args.packet_1],
                   diagnostic_fixture=args.diagnostic_fixture)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                                 encoding="utf-8")
    print(result["comparison_id"])


if __name__ == "__main__":
    main()
