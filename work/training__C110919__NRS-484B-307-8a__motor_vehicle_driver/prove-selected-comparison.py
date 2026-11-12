"""Mutation proof for the selected-pair saved-source comparison boundary."""
import copy
import hashlib
import json
from pathlib import Path

from selected_comparison_audit import compare, load

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejects(left, right):
    try:
        compare(left, right, diagnostic=True)
    except ValueError as error:
        return str(error)
    raise AssertionError("Damaged comparison was accepted")


def main():
    left = load("reference", diagnostic=True)
    right = load("contrast", diagnostic=True)
    result = compare(left, right, diagnostic=True)
    if result["passed"] is not False or result["source_comparison_passed"] is not True:
        raise AssertionError("Diagnostic comparison claimed original acceptance")
    negatives = {}
    damaged = copy.deepcopy(right)
    damaged["evidence"][0]["world"]["weather"] = "rain"
    negatives["weather_changed"] = rejects(left, damaged)
    damaged = copy.deepcopy(right)
    damaged["config"]["duration_s"] = 23
    negatives["capture_config_changed"] = rejects(left, damaged)
    damaged = copy.deepcopy(right)
    damaged["samples"][200]["walker_conflict_occupied"] = True
    negatives["pedestrian_context_changed"] = rejects(left, damaged)
    try:
        load("reference", diagnostic=False)
    except ValueError as error:
        negatives["synthetic_as_original"] = str(error)
    else:
        raise AssertionError("Synthetic comparison promoted to original")
    proof = {"format": "c110919-selected-comparison-cpu-proof-v1",
             "manifest_sha256": sha(HERE / "update017-selected-pair-probe-manifest.json"),
             "auditor_sha256": sha(HERE / "selected_comparison_audit.py"),
             "positive": result, "negative_rejections": negatives,
             "original_comparison_accepted": False}
    path = HERE / "update021-selected-comparison-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"source_comparison_passed": True,
                      "negative_rejections": len(negatives), "proof_sha256": sha(path),
                      "original_comparison_accepted": False}))


if __name__ == "__main__":
    main()
