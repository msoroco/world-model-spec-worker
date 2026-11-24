"""Independent exact selected-case source, receipt, and comparison audit."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "selected-v2-manifest.json"
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def embedded(bundle, name):
    matches = [item["content"] for item in bundle["files"] if item["path"] == name]
    assert len(matches) == 1, name
    return matches[0]


def checked_receipt(ref):
    path = ROOT / ref["path"]
    assert path.is_file() and sha(path) == ref["sha256"], str(path)
    return path


manifest = json.loads(MANIFEST.read_text())
plan = json.loads((ROOT / "case-plan.json").read_text())
assert manifest["format"] == "worker-execution-manifest"
assert manifest["assignment_id"] == ROOT.name
assert manifest["selected_case_ids"] == [case["case_id"] for case in manifest["cases"]]
assert manifest["selected_case_ids"] == [case["case_id"] for case in plan["cases"]]
assert len(manifest["cases"]) == 2
assert len(manifest["comparisons"]) == len(plan["comparisons"]) == 1
assert manifest["comparisons"][0]["comparison_id"] == plan["comparisons"][0]["comparison_id"]
assert manifest["comparisons"][0]["case_ids"] == plan["comparisons"][0]["case_ids"]
assert manifest["comparisons"][0]["deliberate_differences"] == plan["comparisons"][0]["deliberate_differences"]
assert manifest["comparisons"][0]["isolation_audit"] == "selected-v2/audit.json"
comparison_acceptance = manifest["comparisons"][0]["original_comparison_audit"]
assert sha(ROOT / comparison_acceptance["script"]) == comparison_acceptance["script_sha256"]
checked_receipt(comparison_acceptance["positive_cpu_test"])
negative_comparison = checked_receipt(comparison_acceptance["negative_cpu_test"]).read_text()
assert comparison_acceptance["negative_expected_error"] in negative_comparison
assert not comparison_acceptance["physical_acceptance_claimed"]
assert all("pending" not in condition for condition in manifest["comparisons"][0]["fixed_conditions"])
assert not manifest["physical_acceptance_claimed"] and not manifest["legal_verdict_claimed"]
semantic_index = json.loads(checked_receipt(manifest["semantic_proposal_index"]).read_text())
assert semantic_index["format"] == "worker-semantic-delivery"
assert set(semantic_index["stages"]) == {"relevance_batch", "relevance", "template", "judgment_observables", "bindings", "cases"}
for reference in semantic_index["stages"].values():
    for item in reference if isinstance(reference, list) else [reference]:
        checked_receipt(item)

bundles = []
configs = []
routes = []
results = []
for index, case in enumerate(manifest["cases"], 1):
    assert case["kind"] == "delivery"
    acceptance = case["delivery_acceptance"]
    assert acceptance["case_id"] == case["case_id"] and acceptance["sets"] == ["full-train"]
    assert acceptance["script_sha256"] == sha(ROOT / acceptance["script"])
    assert acceptance["test_exit_code"] == 0 and acceptance["negative_exit_code"] != 0
    assert sha(ROOT / acceptance["test_log"]) == acceptance["test_log_sha256"]
    assert sha(ROOT / acceptance["negative_log"]) == acceptance["negative_log_sha256"]
    assert acceptance["negative_expected_error"] in (ROOT / acceptance["negative_log"]).read_text()
    source = ROOT / case["construction"]
    assert sha(source) == case["construction_sha256"]
    bundle = json.loads(source.read_text())
    assert bundle["case_id"] == case["case_id"]
    bundles.append(bundle)
    config = json.loads(embedded(bundle, "config.json"))
    configs.append(config)
    assert config["case_id"] == case["case_id"]
    assert config["duration_s"] == 30 and config["rate_hz"] == 20
    assert len(config["cameras"]) == 4
    route = [json.loads(line) for line in embedded(bundle, "authored-route.jsonl").splitlines()]
    routes.append(route)
    assert len(route) == 600 and [row["frame"] for row in route] == list(range(600))
    assert {row["lane_id"] for row in route} == {-index}
    assert all(row["source_kind"] == "authored_native_request" and not row["actual_exit_observed"] and not row["roundabout_verified"] for row in route)
    assert len(case["candidates"]) == 1 and case["candidates"][0]["id"] == "fallback1"
    candidate = case["candidates"][0]
    alt_source = ROOT / candidate["construction"]
    assert sha(alt_source) == candidate["construction_sha256"]
    alt = json.loads(alt_source.read_text())
    assert {item["path"] for item in bundle["files"]} == {item["path"] for item in alt["files"]}
    assert all(embedded(bundle, name) == embedded(alt, name) for name in {item["path"] for item in bundle["files"]} - {"runner.py"})
    old = "ego.apply_control(control_to(carla, ego, lookahead, 6))"
    new = "ego.apply_control(control_to(carla, ego, lookahead, 7.5))"
    assert old in embedded(bundle, "runner.py")
    assert embedded(alt, "runner.py") == embedded(bundle, "runner.py").replace(old, new)
    for label, expected_hash, refs in (("primary", case["construction_sha256"], case["primary_proofs"]), ("fallback1", candidate["construction_sha256"], candidate["proofs"])):
        offline = checked_receipt(refs["offline"]).read_text()
        compatibility = json.loads(checked_receipt(refs["compatibility"]).read_text())
        negative = checked_receipt(refs["missing_source_negative"]).read_text()
        processing = json.loads(checked_receipt(refs["recorded_only_processing"]).read_text())
        assert "Ran 4 tests" in offline and "OK" in offline
        assert compatibility["passed"] and len(compatibility["checks"]) == 11
        assert compatibility["candidate_id"] == label and compatibility["construction_sha256"] == expected_hash
        assert compatibility["negative_error_contains"] in negative
        assert "Missing required source: roundabout-track.jsonl" in negative
        assert processing["passed"] and processing["recorded_only"]
        assert processing["candidate_id"] == label
        assert processing["native_revision"]["construction_sha256"] == expected_hash
        assert not processing["physical_acceptance_claimed"]
        results.append({"case_id": case["case_id"], "candidate": label, "construction_sha256": expected_hash, "compatibility_sha256": refs["compatibility"]["sha256"], "processing_sha256": refs["recorded_only_processing"]["sha256"]})

file_names = {item["path"] for item in bundles[0]["files"]}
assert file_names == {item["path"] for item in bundles[1]["files"]}
assert {name for name in file_names if embedded(bundles[0], name) != embedded(bundles[1], name)} == {"config.json", "authored-route.jsonl"}
allowed_config_differences = {"case_id", "selected_case_id", "case", "track_sha256"}
assert {key for key in configs[0] if configs[0][key] != configs[1][key]} == allowed_config_differences
assert [row["frame"] for row in routes[0]] == [row["frame"] for row in routes[1]]
assert [row["time_s"] for row in routes[0]] == [row["time_s"] for row in routes[1]]
allowed_route_differences = {"witness", "lane_id", "ego_x_m", "ego_y_m", "ego_heading_deg", "road_id", "phase"}
assert {key for left, right in zip(*routes) for key in left if left[key] != right[key]} <= allowed_route_differences
assert plan["comparisons"][0]["deliberate_differences"] == ["roundabout_exit_lane"]
for ref in manifest["independent_cpu_audits"]:
    checked_receipt(ref)
print(json.dumps({"passed": True, "selected_manifest_sha256": sha(MANIFEST), "selected_case_count": 2, "case_candidate_proofs": results, "comparison_variable": "roundabout_exit_lane", "fixed_file_contract": sorted(file_names - {"config.json", "authored-route.jsonl"}), "allowed_route_differences": sorted(allowed_route_differences), "physical_acceptance_claimed": False}))
