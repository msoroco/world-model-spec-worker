"""Source-bound two-pair audit of original median-opening entry timing."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from entry_timing import measure

ROOT = Path(__file__).resolve().parent
SUFFIXES = ("entry_below", "entry_inside", "entry_above")
FIXED = ("map_source_sha256", "intersection_source_sha256",
         "highway_source_sha256", "device_source_sha256",
         "ego_road_id", "other_road_id", "ego_actor_id", "other_actor_id",
         "intersection_polygon_xy_m")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(source_map):
    plan = json.loads((ROOT / "case-plan.json").read_text())
    expected = {ROOT.name + "__" + suffix for suffix in SUFFIXES}
    if set(source_map) != expected:
        raise ValueError("all three exact original timing packets required")
    packets, measured = {}, {}
    for case in expected:
        path = Path(source_map[case]).resolve()
        packet = json.loads(path.read_text())
        if packet.get("diagnostic_fixture") is True or packet.get("source_kind") != "original_native":
            raise ValueError("synthetic timing source cannot satisfy original comparison")
        packets[case] = packet
        measured[case] = measure(path, sha(path), case_id=case, expected_frames=900)
    pairs = []
    for comparison in plan["comparisons"]:
        left, right = comparison["case_ids"]
        if any(packets[left].get(key) != packets[right].get(key) for key in FIXED):
            raise ValueError("timing comparison changed fixed map, actors or control source")
        l = measured[left]["intersection_entry_time_difference_s"]
        r = measured[right]["intersection_entry_time_difference_s"]
        if l >= r:
            raise ValueError("original measured entry timing did not preserve planned order")
        pairs.append({"comparison_id": comparison["comparison_id"],
                      "case_ids": [left, right],
                      "source_sha256": {case: measured[case]["original_trace_sha256"]
                                        for case in (left, right)},
                      "fixed_source_checks_passed": True,
                      "measured_entry_difference_s": {left: l, right: r},
                      "legal_approximately_same_time": "undetermined",
                      "official_device_exception": "undetermined"})
    return {"format": "c125745-original-entry-comparison-audit-v1",
            "assignment_id": ROOT.name, "comparisons": pairs,
            "legal_applicability": "unresolved", "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite original comparison report")
    report = audit(json.loads(args.source_map.read_text()))
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
