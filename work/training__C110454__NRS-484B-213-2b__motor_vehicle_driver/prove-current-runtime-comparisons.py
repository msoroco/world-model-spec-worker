"""Exercise selected comparison boundary on retained CPU diagnostic sources."""
import copy
import hashlib
import json
import os

from comparison_audit import HERE, PAIRS, audit, load_side
import comparison_audit
from saved_comparison_audit import compare_sources

comparison_audit.MANIFEST = HERE / 'current-runtime-reproof-manifest.json'


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
    selected = set(os.environ.get('C110454_COMPARISON_FILTER', '').split(',')) - {''}
    for kind, suffixes in PAIRS.items():
        if selected and kind not in selected:
            continue
        paths = []
        for suffix in suffixes:
            proof_dir = HERE / 'current-runtime-selected-proof' / suffix / 'primary'
            receipt_sha = hashlib.sha256((proof_dir / 'compatibility.json').read_bytes()).hexdigest()
            attempts = [candidate for candidate in (root / '.runtime-work').glob(
                f'c110454-current-{suffix}-primary-*-compat')
                if (candidate / 'compatibility.json').is_file() and
                hashlib.sha256((candidate / 'compatibility.json').read_bytes()).hexdigest() == receipt_sha]
            if not attempts:
                raise ValueError('Current comparison source missing: ' + suffix)
            attempt = max(attempts, key=lambda candidate: candidate.stat().st_mtime_ns)
            saved = proof_dir / 'saved-command.log' 
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
                else "Held road or route contrast differs")
        results.append({"comparison_id": result["comparison_id"],
                        "lateral_changed_frames": result["lateral_changed_frames"],
                        "speed_changed_frames": result["speed_changed_frames"],
                        "accepted": False})
    proof = {"format": "c110454-original-comparison-cpu-proof-v1",
             "diagnostic_comparisons": results,
             "negative_checks": ["synthetic_as_original_all_5", "changed_weather_all_5",
                                 "changed_capture_config_all_5", "changed_declared_difference_all_5"],
             "original_comparisons_accepted": 0}
    path = HERE / ("current-runtime-comparison-" + '-'.join(sorted(selected)) + ".json"
                   if selected else "current-runtime-original-comparison-proof.json")
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"comparisons": len(results),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
