"""Reopen two sealed saved arrow-turn attempts for a planned comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import PAIRS, audit_pair
from saved_turn import audit_saved_attempt


def audit_saved_pair(comparison_id, left_root, left_manifest_ref,
                     right_root, right_manifest_ref, *, expected_frames=600,
                     diagnostic=False):
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact red-plus-arrow comparison")
    if (left_root == right_root and
            left_manifest_ref.get("sha256") == right_manifest_ref.get("sha256")):
        raise ValueError("same original attempt reused for comparison")
    left = audit_saved_attempt(left_root, left_manifest_ref,
                               expected_frames=expected_frames,
                               diagnostic=diagnostic)
    right = audit_saved_attempt(right_root, right_manifest_ref,
                                expected_frames=expected_frames,
                                diagnostic=diagnostic)
    receipt = audit_pair(comparison_id, left["comparison_row"],
                         right["comparison_row"])
    receipt.update({
        "format": "c111610-source-bound-red-arrow-comparison-v1",
        "case_suffixes": [left["case_suffix"], right["case_suffix"]],
        "source_hashes": {
            "left": {"manifest": left["manifest_sha256"],
                     "site": left["site_sha256"],
                     "telemetry": left["telemetry_sha256"]},
            "right": {"manifest": right["manifest_sha256"],
                      "site": right["site_sha256"],
                      "telemetry": right["telemetry_sha256"]},
        },
        "decoded_view_frames": sum(v["frames"] for v in left["decoded_cameras"].values()) +
                               sum(v["frames"] for v in right["decoded_cameras"].values()),
    })
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left-attempt', type=Path, required=True)
    parser.add_argument('--right-attempt', type=Path, required=True)
    args = parser.parse_args()
    def ref(root):
        path = root / 'manifest.json'
        return {'path': 'manifest.json',
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    receipt = audit_saved_pair(args.comparison, args.left_attempt, ref(args.left_attempt),
                               args.right_attempt, ref(args.right_attempt))
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
