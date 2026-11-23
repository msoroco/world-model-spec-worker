"""Compare two separately accepted original parking attempts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_comparison_audit import PAIRS, audit
from parking_delivery_audit import audit_attempt


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_pair(comparison_id: str, left: dict, right: dict,
                left_delivery: dict, right_delivery: dict) -> dict:
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact comparison")
    first, second, _ = PAIRS[comparison_id]
    for source, receipt, suffix in ((left, left_delivery, first),
                                    (right, right_delivery, second)):
        case_id = ROOT.name + "__" + suffix
        if (source.get("case_id") != case_id or
                source.get("diagnostic_fixture") is not False or
                receipt.get("format") != "worker-delivery-audit" or
                receipt.get("passed") is not True or
                receipt.get("case_id") != case_id or
                set(receipt.get("checks", {})) != {
                    "native_source", "all_participants", "time_join",
                    "full_video_decode", "actual_pixels", "physical_completion"} or
                not all(receipt["checks"].values())):
            raise ValueError("independent original case acceptance missing: " + case_id)
        if (receipt.get("source_audit_sha256") != sha(ROOT / "parking_delivery_audit.py") or
                receipt.get("delivery_auditor_sha256") != sha(ROOT / "independent" / "delivery_audit.py")):
            raise ValueError("original acceptance auditor revision changed")
    measured = audit(left["saved_observations"], right["saved_observations"], comparison_id)
    if measured.get("physical_acceptance_claimed") is not False:
        raise ValueError("comparison result must retain engineering-only scope")
    return {"format": "worker-original-comparison-audit", "passed": True,
            "comparison_id": comparison_id, "case_ids": measured["case_ids"],
            "source_packet_sha256": measured["source_packet_sha256"],
            "original_history_sha256": measured["original_history_sha256"],
            "measurement": measured,
            "delivery_receipt_sha256": [left_delivery["receipt_sha256"],
                                        right_delivery["receipt_sha256"]],
            "legal_judgment": "unresolved"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-id", required=True, choices=tuple(PAIRS))
    parser.add_argument("--baseline-attempt", required=True, type=Path)
    parser.add_argument("--changed-attempt", required=True, type=Path)
    parser.add_argument("--baseline-delivery", required=True, type=Path)
    parser.add_argument("--changed-delivery", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.baseline_attempt.resolve() == args.changed_attempt.resolve():
        raise ValueError("comparison reuses one original attempt")
    sources = [audit_attempt(path) for path in
               (args.baseline_attempt, args.changed_attempt)]
    receipts = []
    for attempt, path in ((args.baseline_attempt, args.baseline_delivery),
                          (args.changed_attempt, args.changed_delivery)):
        receipt = json.loads(path.read_text())
        if (receipt.get("source_result_sha256") != sha(attempt / "result.json") or
                receipt.get("video_sha256") != sha(attempt / "raw.mkv") or
                receipt.get("trace_sha256") != sha(attempt / "traffic_spec" / "trace.json") or
                receipt.get("frame_map_sha256") != sha(attempt / "video_frames.jsonl")):
            raise ValueError("original delivery receipt source changed")
        receipt["receipt_sha256"] = sha(path)
        receipts.append(receipt)
    result = verify_pair(args.comparison_id, *sources, *receipts)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("original comparison audit passed: " + args.comparison_id)


if __name__ == "__main__":
    main()
