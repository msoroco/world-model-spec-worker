"""CPU prove current four saved-source comparisons and rejection branches."""
import copy
import hashlib
import json

from saved_comparison_audit import HERE, PAIRS, audit_pair, compare_sources, load_side, read


def rejects(call, expected):
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError("Wrong rejection: " + str(error)) from error
    else:
        raise AssertionError("Expected rejection: " + expected)


def sides(kind):
    a, b, manifest_name, root_name, group = PAIRS[kind]
    manifest = read(HERE / manifest_name)
    return (load_side(group, a, manifest, root_name, diagnostic=True),
            load_side(group, b, manifest, root_name, diagnostic=True))


def main():
    results = []
    for kind in PAIRS:
        result = audit_pair(kind, diagnostic=True)
        assert result["source_comparison_passed"] and not result["passed"]
        assert result["diagnostic_fixture"] and not result["physical_or_legal_acceptance_claimed"]
        assert len(result["source_bindings"]) == 2
        rejects(lambda kind=kind: audit_pair(kind),
                "Synthetic source cannot establish original Native delivery")
        results.append({key: result[key] for key in
                        ("comparison_id", "case_ids", "source_bindings",
                         "lateral_changed_frames", "speed_changed_frames")})
    left, right = sides("main")
    changed = copy.deepcopy(right)
    changed["evidence"][0]["world"]["weather"] = "changed"
    rejects(lambda: compare_sources("main", left, changed),
            "Held frame/time map or weather differs")
    changed = copy.deepcopy(right)
    changed["samples"] = copy.deepcopy(left["samples"])
    rejects(lambda: compare_sources("main", left, changed),
            "Held road or lateral contrast differs")
    changed = copy.deepcopy(right)
    changed["config"]["rate_hz"] = 10
    rejects(lambda: compare_sources("main", left, changed),
            "Held exact capture or controller config differs")
    left, right = sides("oneway")
    changed = copy.deepcopy(right)
    changed["road"]["one_way_native_readback"] = False
    rejects(lambda: compare_sources("oneway", left, changed),
            "One-way designation contrast or fixed route differs")
    left, right = sides("traversal")
    changed = copy.deepcopy(right)
    changed["samples"][-1]["native_center_xy_m"][0] += 1
    rejects(lambda: compare_sources("traversal", left, changed),
            "Held longitudinal route differs")
    proof = {"format": "c110454-saved-comparison-cpu-proof-v1",
             "comparison_count": len(results), "comparisons": results,
             "negative_checks": ["synthetic_as_original_all_4", "changed_weather",
                                 "missing_lateral_contrast", "changed_capture_config",
                                 "wrong_oneway_designation", "changed_traversal_endpoint"],
             "selected_or_accepted": False}
    path = HERE / "update018-saved-comparison-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"comparison_count": len(results),
                      "negative_checks": proof["negative_checks"],
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
