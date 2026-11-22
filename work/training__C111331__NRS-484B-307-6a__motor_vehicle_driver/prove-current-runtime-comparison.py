"""Source-bound current yellow/red entry diagnostic comparison with negatives."""
import hashlib
import json
from pathlib import Path

import comparison_audit as audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject(call, expected):
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise
    else:
        raise ValueError("Changed comparison source accepted: " + expected)


def main():
    reference = ROOT / ".runtime-work/c111331-current-reference-primary-compat"
    contrast = ROOT / ".runtime-work/c111331-current-matrix/contrast/primary/compat"
    result = audit.audit(reference, contrast, diagnostic=True)
    if not result["passed"] or not result["diagnostic_only"] or result["physical_acceptance_claimed"]:
        raise ValueError("Diagnostic comparison scope differs")
    reject(lambda: audit.audit(reference, contrast), "Original Native sources required for physical comparison")
    original_read = audit.read
    def changed_config(path):
        item = original_read(path)
        if Path(path) == contrast / "config.json":
            item["knobs"]["speed_m_per_frame"] += 1
        return item
    audit.read = changed_config
    try:
        reject(lambda: audit.audit(reference, contrast, diagnostic=True),
               "Fixed vehicle motion policy differs")
    finally:
        audit.read = original_read
    original_rows = audit.rows
    def changed_request(path):
        item = original_rows(path)
        if Path(path) == contrast / "native-requests.jsonl":
            item[0]["native_center_xy_m"][0] += 1
        return item
    audit.rows = changed_request
    try:
        reject(lambda: audit.audit(reference, contrast, diagnostic=True),
               "Fixed request differs: native_center_xy_m")
    finally:
        audit.rows = original_rows
    output = HERE / "current-runtime-selected-comparison-proof.json"
    output.write_text(json.dumps({"format": "c111331-current-comparison-proof-v1",
                                  "manifest_sha256": sha(HERE / "current-runtime-reproof-manifest.json"),
                                  "comparison": result,
                                  "negative_rejections": ["synthetic_as_original", "changed_motion_policy",
                                                          "changed_fixed_request"],
                                  "original_native_or_legal_acceptance_claimed": False}, indent=2) + "\n")
    print(json.dumps({"comparison_id": result["comparison_id"],
                      "negative_rejections": 3, "proof_sha256": sha(output)}))


if __name__ == "__main__":
    main()
