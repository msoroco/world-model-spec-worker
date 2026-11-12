"""Source-shaped positive and damaged-source rejection proof for absent pair."""
import copy
import hashlib
import json
from pathlib import Path

from absent_reference_comparison import compare, load

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejects(left, right):
    try:
        compare(left, right, diagnostic=True)
    except ValueError as error:
        return str(error)
    raise AssertionError("Damaged absent-reference comparison was accepted")


def main():
    left = load("absent_reference", diagnostic=True)
    right = load("absent_reference_contrast", diagnostic=True)
    positive = compare(left, right, diagnostic=True)
    if positive["passed"] is not False or positive["source_comparison_passed"] is not True:
        raise AssertionError("Diagnostic claimed original acceptance")
    negatives = {}
    damaged = copy.deepcopy(right)
    damaged["evidence"][0]["world"]["weather"] = "rain"
    negatives["weather_changed"] = rejects(left, damaged)
    damaged = copy.deepcopy(right)
    damaged["config"]["duration_s"] = 23
    negatives["capture_config_changed"] = rejects(left, damaged)
    damaged = copy.deepcopy(right)
    damaged["samples"][200]["walker_conflict_occupied"] = True
    negatives["pedestrian_changed"] = rejects(left, damaged)
    damaged = copy.deepcopy(right)
    damaged["samples"][159]["signal_state_observed"] = "Green"
    negatives["signal_changed"] = rejects(left, damaged)
    damaged = copy.deepcopy(left)
    damaged["road"]["stop_line_y_m"] = -6.0
    negatives["stop_line_inserted"] = rejects(damaged, right)
    damaged = copy.deepcopy(left)
    damaged["road"]["stopping_reference_y_m"] = -14.0
    negatives["boundary_changed"] = rejects(damaged, right)
    damaged = copy.deepcopy(right)
    damaged["samples"][210]["native_center_xy_m"][1] += .5
    negatives["late_motion_changed"] = rejects(left, damaged)
    damaged = copy.deepcopy(right)
    damaged["result"]["measured_values"]["stop"]["first_front_crossing_frame"] = 160
    negatives["forged_stop_measurement"] = rejects(left, damaged)
    try:
        load("absent_reference", diagnostic=False)
    except ValueError as error:
        negatives["synthetic_as_original"] = str(error)
    else:
        raise AssertionError("Synthetic source was promoted to original")
    proof = {"format": "c110919-absent-reference-comparison-cpu-proof-v1",
             "manifest_sha256": sha(HERE / "draft-absent-reference-execution-manifest.json"),
             "auditor_sha256": sha(HERE / "absent_reference_comparison.py"),
             "positive": positive, "negative_rejections": negatives,
             "original_comparison_accepted": False}
    path = HERE / "update030-absent-comparison-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"source_comparison_passed": True,
                      "negative_rejections": len(negatives),
                      "proof_sha256": sha(path), "original_comparison_accepted": False}))


if __name__ == "__main__":
    main()
