"""Saved-only freight measurement; original source bytes are never rewritten."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from freight_contract import audit_source_bundle
from saved_delivery import audit_delivery


def measure_freight_branch(attempt: Path, manifest: dict) -> dict:
    case_id = manifest["case_id"]
    variant = case_id.rsplit("__", 1)[-1]
    measured = audit_source_bundle(manifest, case_id=case_id, variant=variant,
                                   source_root=attempt, require_raw=True)
    return {"observed_action": measured["observed_action"],
            "commercial_status_reviewed": measured["commercial_status_reviewed"],
            "stopped_inside_zone": measured["stopped_inside_zone"],
            "inside_posted_window": measured["inside_posted_window"],
            "final_halt_duration_s": measured["final_halt_duration_s"],
            "legal_conclusion": "unresolved"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(attempt: Path, output: Path) -> dict:
    attempt = Path(attempt).resolve(strict=True)
    for name in ("freight-delivery-manifest.json", "freight-native-source.json",
                 "freight_motion.jsonl"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    manifest = json.loads((attempt / "freight-delivery-manifest.json").read_text(encoding="utf-8"))
    measured = audit_delivery(manifest, attempt_root=attempt)
    branch = measure_freight_branch(attempt, manifest)
    source_names = ("freight-delivery-manifest.json", "freight-native-source.json",
                    "freight_motion.jsonl")
    report = {
        "format": "worker-freight-saved-analysis-v1",
        "case_id": measured["case_id"],
        "diagnostic_fixture": False,
        "physical_completion": measured["physical_case_completion"],
        "source_integrity": measured["source_integrity"],
        "full_video_decode": measured["full_video_decode"],
        "actual_pixels_reviewed": False,
        "legal_judgment": "unresolved_review",
        "measurements": {
            "freight_branch_observation": {
                "value": branch, "method": "measure_freight_branch",
                "sources": {name: sha(attempt / name) for name in source_names},
            },
            "freight_original_frames": {
                "value": measured["frames_checked"], "unit": "frames",
                "method": "sealed original Native motion and camera frame join",
                "reference": "freight_motion.jsonl",
            },
            "freight_physical_completion": {
                "value": measured["physical_case_completion"], "unit": "boolean",
                "method": "source-bound exact freight case completion check",
                "reference": "freight-native-source.json",
            },
        },
    }
    output = Path(output)
    if output.exists():
        raise ValueError("retain prior saved analysis; choose fresh output")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
