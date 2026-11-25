"""Audit one exact pedestrian comparison from two sealed saved attempts.

The CLI recomputes both source projections; it never infers a legal verdict.
Diagnostic mode is explicit and its receipt cannot claim delivery acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import ALLOWED_DIFFS, _audit_packets
from saved_measurement import comparison_projection


def compare(plan_path, comparison_id, first_root, second_root, *, diagnostic=False):
    plan = json.loads(Path(plan_path).read_text())
    selected = [item for item in plan["comparisons"]
                if item["comparison_id"] == comparison_id]
    if len(selected) != 1 or comparison_id not in ALLOWED_DIFFS:
        raise ValueError("unknown exact comparison")
    pair = selected[0]["case_ids"]
    if len(pair) != 2 or pair[0] == pair[1]:
        raise ValueError("exact two-case comparison required")
    roots = (Path(first_root), Path(second_root))
    packets = {case: comparison_projection(root, case)
               for case, root in zip(pair, roots)}
    if not diagnostic and any(packet["source_kind"] != "original_saved_acquisition"
                              for packet in packets.values()):
        raise ValueError("original saved acquisition required")
    if diagnostic and any(packet["source_kind"] != "synthetic_fixture"
                          for packet in packets.values()):
        raise ValueError("diagnostic mode requires explicit synthetic fixtures")
    sources = {case: {"sha256": packets[case]["source_packet_sha256"]}
               for case in pair}
    result = _audit_packets({"comparisons": [selected[0]]}, packets, sources)
    result.update({"format": "worker-pedestrian-saved-comparison",
                   "comparison_id": comparison_id,
                   "diagnostic_fixture": diagnostic,
                   "delivery_acceptance_claimed": False,
                   "attempt_roots": [str(root.resolve()) for root in roots],
                   "plan_sha256": hashlib.sha256(Path(plan_path).read_bytes()).hexdigest()})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    result = compare(args.plan, args.comparison, args.first, args.second,
                     diagnostic=args.diagnostic)
    if args.output.exists():
        raise ValueError("retain prior comparison receipt")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
