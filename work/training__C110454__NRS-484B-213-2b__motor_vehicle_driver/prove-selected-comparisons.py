"""Prove three current selected controlled comparisons from saved sources."""
import copy
import hashlib
import json

from selected_comparison_audit import HERE, MANIFEST, PAIRS, audit_pair, load_side
from saved_comparison_audit import compare_sources
from source_join_audit import read


def rejects(call, expected):
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError("Wrong rejection: " + str(error)) from error
    else:
        raise AssertionError("Expected rejection: " + expected)


def main():
    manifest = read(MANIFEST)
    results = []
    for kind, (a, b) in PAIRS.items():
        result = audit_pair(kind, diagnostic=True)
        assert result["source_comparison_passed"] and not result["passed"]
        assert result["diagnostic_fixture"] and not result["physical_or_legal_acceptance_claimed"]
        rejects(lambda kind=kind: audit_pair(kind),
                "Synthetic source cannot establish original Native delivery")
        left = load_side(a, manifest, diagnostic=True)
        right = load_side(b, manifest, diagnostic=True)
        changed = copy.deepcopy(right)
        changed["evidence"][0]["world"]["weather"] = "changed"
        rejects(lambda kind=kind, left=left, changed=changed:
                compare_sources(kind, left, changed),
                "Held frame/time map or weather differs")
        results.append({"kind": kind, "comparison_id": result["comparison_id"],
                        "manifest_sha256": result["manifest_sha256"],
                        "source_bindings": result["source_bindings"],
                        "lateral_changed_frames": result["lateral_changed_frames"],
                        "speed_changed_frames": result["speed_changed_frames"]})
    proof = {"format": "c110454-selected-comparison-cpu-proof-v1",
             "comparison_count": 3, "comparisons": results,
             "negative_checks": ["synthetic_as_original_all_3",
                                 "changed_held_weather_all_3"],
             "accepted_comparisons": 0}
    path = HERE / "update019-selected-comparison-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"comparison_count": 3,
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
