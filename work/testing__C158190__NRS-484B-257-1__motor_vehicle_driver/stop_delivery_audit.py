"""Independent CPU audit of saved stop attempts; physical acceptance stays open."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from stop_sign_branch import ASSIGNMENT, CASES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def audit(case_id, attempt, receipt_path):
    if case_id not in CASES:
        raise ValueError("exact stop case required")
    context_path = required(attempt, "context.json")
    required(attempt, "original-trace.jsonl")
    camera_path = required(attempt, "cameras.json")
    context = json.loads(context_path.read_text())
    cameras = json.loads(camera_path.read_text())
    proof = json.loads(Path(receipt_path).read_text())
    if (context.get("case_id") != case_id or context.get("control") != "stop_sign" or
            context.get("planned_response") != CASES[case_id] or
            cameras.get("case_id") != case_id or proof.get("case_id") != case_id or
            proof.get("passed") is not True or proof.get("recorded_only") is not True or
            proof.get("originals_preserved") is not True or
            proof.get("timestamp_joins", {}).get("passed") is not True or
            proof.get("final_video_frames") != 9 or
            proof.get("source_kind") != "synthetic_diagnostic_fixture" or
            proof.get("physical_acceptance_claimed") is not False):
        raise ValueError("saved stop diagnostic custody differs")
    return {"case_id": case_id, "source_kind": "synthetic_diagnostic_fixture",
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "context_sha256": sha(context_path), "camera_manifest_sha256": sha(camera_path),
            "saved_receipt_sha256": sha(receipt_path), "physical_acceptance": "unverified",
            "legal_acceptance": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.case, args.attempt, args.receipt)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": args.case, "source_kind": result["source_kind"],
                      "physical_acceptance": result["physical_acceptance"]}, sort_keys=True))


if __name__ == "__main__":
    main()
