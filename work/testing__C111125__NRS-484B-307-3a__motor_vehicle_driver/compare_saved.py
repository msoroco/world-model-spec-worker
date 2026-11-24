"""Independently compare one declared pair of saved Native attempts.

The diagnostic switch exercises the same saved-source checks on labelled CPU
fixtures. Neither path determines permission, lawful use, or right of way.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from comparison_audit import PAIRS, audit_pair
from delivery_audit import audit as audit_delivery
from run_diagnostic_comparisons import load, sha


def native_custody(root):
    provenance = json.loads((root / "acquisition-provenance.json").read_text())
    if provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is not False:
        raise ValueError("original Native acquisition provenance required")
    seal_path = root / "capture-seal.json"
    seal = json.loads(seal_path.read_text())
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("provenance_kind") != "native" or
            seal.get("diagnostic_fixture") is not False or
            seal.get("events") != ["capture_finished", "encoders_closed",
                                   "restoration_verified"] or
            seal.get("restoration", {}).get("restored") is not True or
            seal.get("frames") != 900):
        raise ValueError("original Native capture seal required")
    for name, checksum in seal.get("sources", {}).items():
        source = (root / name).resolve()
        if not source.is_relative_to(root) or not source.is_file() or sha(source) != checksum:
            raise ValueError("sealed original source differs: " + name)
    if not seal.get("sources"):
        raise ValueError("Native capture seal lacks original sources")
    return sha(seal_path)


def compare(comparison_id, left_path, right_path, *, diagnostic=False,
            negative_fixed_condition=False):
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact comparison")
    if negative_fixed_condition and not diagnostic:
        raise ValueError("negative fixed-condition probe requires diagnostic fixture")
    left_root, right_root = Path(left_path).resolve(), Path(right_path).resolve()
    if left_root == right_root:
        raise ValueError("comparison needs two independently saved attempts")
    prefix = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__"
    left_suffix, right_suffix = PAIRS[comparison_id][:2]
    cases = (prefix + left_suffix, prefix + right_suffix)
    seals = [None, None] if diagnostic else [native_custody(root)
                                            for root in (left_root, right_root)]
    delivery = [audit_delivery(root, case, diagnostic=diagnostic)
                for root, case in zip((left_root, right_root), cases)]
    observed = [load(root) for root in (left_root, right_root)]
    if negative_fixed_condition:
        observed[1]["signal_survey_sha256"] = "0" * 64
    checked = audit_pair(comparison_id, *observed)
    return {"format": "dual-green-saved-comparison", "comparison_id": comparison_id,
            "case_ids": list(cases), "diagnostic_fixture": diagnostic,
            "native_source_checked": not diagnostic,
            "source_frames_checked": checked["source_frames_checked"],
            "attempts": [{"case_id": case, "source_sha256": record["source_sha256"],
                          "result_sha256": receipt["result_sha256"],
                          "handoff_sha256": receipt["handoff_sha256"],
                          "capture_seal_sha256": seal_hash}
                         for case, record, receipt, seal_hash in zip(cases,
                                                                      observed, delivery,
                                                                      seals)],
            "fixed_conditions_verified": True, "declared_difference_verified": True,
            "physical_acceptance_claimed": False,
            "permission_verdict": None, "right_of_way_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=tuple(PAIRS), required=True)
    parser.add_argument("--left-attempt", type=Path, required=True)
    parser.add_argument("--right-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--negative-fixed-condition", action="store_true")
    args = parser.parse_args()
    report = compare(args.comparison, args.left_attempt, args.right_attempt,
                     diagnostic=args.diagnostic_fixture,
                     negative_fixed_condition=args.negative_fixed_condition)
    if args.output.exists():
        raise ValueError("retain prior comparison receipt")
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print("saved comparison passed: " + args.comparison)


if __name__ == "__main__":
    main()
