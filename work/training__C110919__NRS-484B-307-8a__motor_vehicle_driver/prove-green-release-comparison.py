"""Positive and damaged-source checks for the green-release comparison audit."""
import copy
import hashlib
import json
from pathlib import Path

from green_release_comparison import compare, load

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejects(left, right):
    try:
        compare(left, right, diagnostic=True)
    except ValueError as error:
        return str(error)
    raise AssertionError("Damaged green-release comparison was accepted")


def main():
    left = load("green_release_wait", diagnostic=True)
    right = load("green_release_red_turn", diagnostic=True)
    positive = compare(left, right, diagnostic=True)
    if positive["passed"] is not False or positive["source_comparison_passed"] is not True:
        raise AssertionError("Synthetic comparison claimed original acceptance")
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
    negatives["signal_early"] = rejects(left, damaged)
    damaged = copy.deepcopy(left)
    damaged["samples"][145]["speed_mps"] = .5
    negatives["rolling_before_green"] = rejects(damaged, right)
    damaged = copy.deepcopy(left)
    damaged["road"]["stop_line_y_m"] = -13
    negatives["road_changed"] = rejects(damaged, right)
    try:
        load("green_release_wait", diagnostic=False)
    except ValueError as error:
        negatives["synthetic_as_original"] = str(error)
    else:
        raise AssertionError("Synthetic source was promoted to original")
    proof = {"format": "c110919-green-release-comparison-cpu-proof-v1",
             "manifest_sha256": sha(HERE / "draft-green-release-execution-manifest.json"),
             "auditor_sha256": sha(HERE / "green_release_comparison.py"),
             "positive": positive, "negative_rejections": negatives,
             "original_comparison_accepted": False}
    path = HERE / "update028-green-comparison-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"source_comparison_passed": True,
                      "negative_rejections": len(negatives), "proof_sha256": sha(path),
                      "original_comparison_accepted": False}))


if __name__ == "__main__":
    main()
