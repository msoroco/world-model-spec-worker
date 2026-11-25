"""Compare two independently audited original Native attempts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from comparison_audit import compare_delivery_audits
from independent_cpu_delivery import inspect


def audit_pair(comparison_id: str, reference_attempt: Path,
               variant_attempt: Path) -> dict:
    pairs = {
        "between_intersections_marking": (
            "midblock_unmarked_operating", "midblock_marked_operating"),
        "both_devices_operating": (
            "midblock_unmarked_operating", "midblock_unmarked_inactive"),
    }
    if comparison_id not in pairs:
        raise ValueError("unknown exact comparison")
    left_root = Path(reference_attempt).resolve()
    right_root = Path(variant_attempt).resolve()
    if left_root == right_root:
        raise ValueError("comparison requires distinct original attempts")
    from delivery_audit import PREFIX

    left_case, right_case = (PREFIX + suffix for suffix in pairs[comparison_id])
    left = inspect(left_root, left_case, diagnostic=False)
    right = inspect(right_root, right_case, diagnostic=False)
    result = compare_delivery_audits(comparison_id, left, right)
    result["original_attempts_audited"] = True
    result["full_encoded_camera_decodes"] = 8
    result["legal_verdict"] = None
    result["physical_acceptance"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--reference-attempt", type=Path, required=True)
    parser.add_argument("--variant-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_pair(args.comparison_id, args.reference_attempt,
                        args.variant_attempt)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
