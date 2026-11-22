"""Prove current diagnostic four-point Walk sweep and fixed-source negatives."""
import json
from pathlib import Path

import sweep_comparison_audit as audit
from current_runtime_attempt import locate

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "current-runtime-reproof-manifest.json"

def reject(call, expected):
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise
    else:
        raise AssertionError("Changed sweep source accepted: " + expected)

def main():
    attempts = {suffix: locate(suffix) for suffix in audit.SUFFIXES}
    processing = {suffix: attempt.parent /
                  (attempt.name.removesuffix("-compat") + "-saved") /
                  "v0001/processing.json" for suffix, attempt in attempts.items()}
    for suffix, path in processing.items():
        retained = HERE / "current-runtime-selected-proof" / suffix / "primary/saved-processing.json"
        if audit.sha(path) != audit.sha(retained):
            raise ValueError("Current sweep saved receipt differs: " + suffix)
    result = audit.compare(attempts, processing, diagnostic=True, manifest_path=MANIFEST)
    if result["passed"] or not result["diagnostic_source_shape_passed"]:
        raise AssertionError("Diagnostic sweep claimed original acceptance")
    reject(lambda: audit.compare(attempts, processing, manifest_path=MANIFEST),
           "Original Native Walk source required")
    original_read = audit.read
    def altered_config(path):
        item = original_read(path)
        if Path(path) == attempts[audit.SUFFIXES[1]] / "config.json":
            item["knobs"]["crosswalk_hold_margin_m"] = 3.0
        return item
    audit.read = altered_config
    try:
        reject(lambda: audit.compare(attempts, processing, diagnostic=True,
                                     manifest_path=MANIFEST),
               "Sweep controller setpoints differ")
    finally:
        audit.read = original_read
    original_rows = audit.rows
    def altered_pedestrian(path):
        item = original_rows(path)
        if Path(path) == attempts[audit.SUFFIXES[2]] / "native_samples.jsonl":
            item[120]["pedestrian_body_xy_m"][0][0] += 1.0
        return item
    audit.rows = altered_pedestrian
    try:
        reject(lambda: audit.compare(attempts, processing, diagnostic=True,
                                     manifest_path=MANIFEST),
               "Sweep fixed pedestrian, Walk request or frame time differs")
    finally:
        audit.rows = original_rows
    output = HERE / "current-runtime-sweep-comparison-proof.json"
    output.write_text(json.dumps({
        "format": "c111256-current-sweep-comparison-proof-v1",
        "manifest_sha256": audit.sha(MANIFEST),
        "comparison": result,
        "negative_rejections": ["synthetic_as_original", "changed_setpoint",
                                "changed_pedestrian_body"],
        "original_native_accepted": False
    }, indent=2) + "\n")
    print(json.dumps({"comparison_id": result["comparison_id"],
                      "negative_rejections": 3, "proof_sha256": audit.sha(output)}))

if __name__ == "__main__":
    main()
