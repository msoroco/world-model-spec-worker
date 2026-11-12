"""Exercise selected comparison boundary on retained CPU diagnostic sources."""
import copy
import hashlib
import json

from comparison_audit import HERE, PAIRS, audit, load_side
from saved_comparison_audit import compare_sources


def rejects(action, expected):
    try:
        action()
    except ValueError as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("Expected rejection: " + expected)


def main():
    root = HERE.parents[1]
    results = []
    for kind, suffixes in PAIRS.items():
        paths = []
        for suffix in suffixes:
            attempt = root / ".runtime-work/c110454-update028-six-selected" / suffix / "primary/compatibility"
            saved = HERE / "update028-selected-proofs" / suffix / "primary/process-saved.log"
            paths.extend((attempt, saved))
        result = audit(kind, *paths, diagnostic=True)
        assert result["source_comparison_passed"] and not result["passed"]
        assert not result["delivery_bindings"] and result["diagnostic_fixture"]
        rejects(lambda: audit(kind, *paths),
                "Synthetic source cannot establish original Native delivery")
        left = load_side(suffixes[0], paths[0], paths[1], diagnostic=True)
        right = load_side(suffixes[1], paths[2], paths[3], diagnostic=True)
        changed = copy.deepcopy(right)
        changed["evidence"][0]["world"]["weather"] = "changed"
        rejects(lambda: compare_sources(kind, left, changed),
                "Held frame/time map or weather differs")
        changed = copy.deepcopy(right)
        changed["config"]["duration_s"] = -1
        rejects(lambda: compare_sources(kind, left, changed),
                "Held exact capture or controller config differs")
        changed = copy.deepcopy(right)
        changed["road_xodr_sha256"] = left["road_xodr_sha256"] if kind == "oneway" else "0" * 64
        rejects(lambda: compare_sources(kind, left, changed),
                "One-way designation contrast or fixed route differs" if kind == "oneway"
                else "Held road or lateral contrast differs")
        results.append({"comparison_id": result["comparison_id"],
                        "lateral_changed_frames": result["lateral_changed_frames"],
                        "speed_changed_frames": result["speed_changed_frames"],
                        "accepted": False})
    proof = {"format": "c110454-original-comparison-cpu-proof-v1",
             "diagnostic_comparisons": results,
             "negative_checks": ["synthetic_as_original_all_3", "changed_weather_all_3",
                                 "changed_capture_config_all_3", "changed_declared_difference_all_3"],
             "original_comparisons_accepted": 0}
    path = HERE / "update028-original-comparison-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"comparisons": len(results),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
