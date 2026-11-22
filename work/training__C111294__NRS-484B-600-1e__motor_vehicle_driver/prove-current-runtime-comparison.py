"""Current four-speed diagnostic comparison with original and fixed-source negatives."""
import hashlib
import json
from pathlib import Path

import current_runtime_comparison_audit as audit

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
    attempts = {}
    processing = {}
    for suffix in audit.SUFFIXES:
        if suffix == "below_80_mph":
            attempt = ROOT / ".runtime-work/c111294-current-below-primary-compat"
            receipt = ROOT / ".runtime-work/c111294-current-below-primary-saved/v0001/processing.json"
        else:
            attempt = ROOT / ".runtime-work/c111294-current-matrix" / suffix / "primary/compat"
            receipt = ROOT / ".runtime-work/c111294-current-matrix" / suffix / "primary/saved/v0001/processing.json"
        retained = HERE / "current-runtime-selected-proof" / suffix / "primary/saved-processing.json"
        if sha(receipt) != sha(retained):
            raise ValueError("Current selected saved receipt differs: " + suffix)
        attempts[suffix] = attempt
        processing[suffix] = receipt
    result = audit.compare(attempts, processing, diagnostic=True)
    if result["passed"] is not False or result["diagnostic_source_shape_passed"] is not True:
        raise ValueError("Diagnostic comparison claimed original acceptance")
    reject(lambda: audit.compare(attempts, processing), "Original Native speed source required")
    original_read = audit.read
    def changed_config(path):
        item = original_read(path)
        if Path(path) == attempts["inside_80_mph"] / "config.json":
            item["changed_fixed_context"] = True
        return item
    audit.read = changed_config
    try:
        reject(lambda: audit.compare(attempts, processing, diagnostic=True),
               "Speed comparison changed a fixed construction setting")
    finally:
        audit.read = original_read
    original_rows = audit.read_rows
    def changed_actor(path):
        rows = original_rows(path)
        if Path(path) == attempts["above_80_mph"] / "native_samples.jsonl":
            rows[0]["other_position_m"][0] += 1.0
        return rows
    audit.read_rows = changed_actor
    try:
        reject(lambda: audit.compare(attempts, processing, diagnostic=True),
               "Speed comparison changed fixed actor, traffic or time source")
    finally:
        audit.read_rows = original_rows
    output = HERE / "current-runtime-selected-comparison-proof.json"
    output.write_text(json.dumps({"format": "c111294-current-comparison-proof-v1",
                                  "manifest_sha256": sha(HERE / "current-runtime-reproof-manifest.json"),
                                  "comparison": result,
                                  "negative_rejections": ["synthetic_as_original", "changed_fixed_setting",
                                                          "changed_other_actor_position"],
                                  "original_native_or_legal_acceptance_claimed": False}, indent=2) + "\n")
    print(json.dumps({"comparison_id": result["comparison_id"],
                      "negative_rejections": 3, "proof_sha256": sha(output)}))


if __name__ == "__main__":
    main()
