"""Prove the nine-case semantic proposal against pinned CPU stage contracts."""
import hashlib
import importlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "runtime/pipeline"),
                str(ROOT / "runtime/pipeline/scenario_pipeline")]
from batch_pipeline import stages
from scenario_pipeline.worker_exchange import semantic_delivery


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sampled_distance(entry):
    construction = read(HERE / entry["construction"])
    with tempfile.TemporaryDirectory() as temp:
        for name in ("geometry_base.py", "geometry_statutory.py"):
            (Path(temp) / name).write_text(next(f["content"] for f in construction["files"]
                                                if f["path"] == name))
        sys.path.insert(0, temp)
        try:
            geometry = importlib.import_module("geometry_statutory")
            suffix = entry["case_id"].rsplit("__", 1)[-1]
            return geometry.check()["case_results"][suffix]["nearest_full_body_front_distance_m"]
        finally:
            sys.path.pop(0)
            sys.modules.pop("geometry_statutory", None)
            sys.modules.pop("geometry_base", None)


assignment = read(ROOT / "inputs" / HERE.name / "assignment.json")
manifest_path = HERE / "execution-manifest.json"
manifest = read(manifest_path)
index_path = HERE / "proposals/semantic-index.json"
index = read(index_path)
loaded = {}
for name in ("relevance_batch", "relevance", "template", "bindings", "cases"):
    ref = index["stages"][name]
    source = HERE / ref["path"]
    assert sha(source) == ref["sha256"]
    loaded[name] = read(source)
law = assignment["law_record"]
request = {"cell": assignment["cell"], "actor": assignment["actor"]}
rules = read(stages.ROOT / "data/canonical_parameter_aliases.json")
for name in ("relevance_batch", "relevance"):
    stages.validate(name, loaded[name], {"request": request,
                    "law_records": {assignment["law_id"]: law}, "dependencies": []})
assert loaded["relevance_batch"] == loaded["relevance"]
stages.validate("template", loaded["template"], {
    "request": {"law_id": assignment["law_id"], "actor": assignment["actor"]},
    "law_record": law, "canonical_parameter_rules": rules, "dependencies": []})
stages.validate("bindings", loaded["bindings"], {
    "request": dict(request, template_ids=[loaded["template"]["template_id"]]),
    "canonical_parameter_rules": rules, "dependencies": [loaded["template"]]})
stages.validate("cases", loaded["cases"], {
    "request": request, "dependencies": [loaded["bindings"]],
    "templates": [loaded["template"]], "canonical_parameter_rules": rules,
    "judgment_completion_policy": {}})
selected = {case["case_id"]: case for case in loaded["cases"]["cases"]
            if case["target_type"] != "baseline"}
assert set(selected) == {entry["case_id"] for entry in manifest["cases"]}
for entry in manifest["cases"]:
    assert selected[entry["case_id"]]["recording_description"] == read(
        HERE / entry["construction"])["recording_description"]
rail = {}
for entry in manifest["cases"]:
    suffix = entry["case_id"].rsplit("__", 1)[-1]
    if suffix in ("rail_reference", "rail_at", "rail_contrast"):
        measured = sampled_distance(entry) * 3.280839895
        planned = selected[entry["case_id"]]["variable_assignments"][
            "commanded_left_side_closest_distance_ft"]["value"]
        assert abs(planned - measured) < .005, (suffix, planned, measured)
        rail[suffix] = measured
assert rail["rail_contrast"] < 100 and abs(rail["rail_at"] - 100) < .005
assert rail["rail_reference"] > 100
try:
    semantic_delivery.validate(HERE, assignment, manifest)
except ValueError as exc:
    assert str(exc) == "Assignment lacks exact law text"
else:
    raise AssertionError("Frozen law_record/law mismatch unexpectedly disappeared")
adapted = semantic_delivery.validate(HERE, {**assignment, "law": law}, manifest)
assert adapted["selected_cases"] == 9 and adapted["stage_count"] == 5
proof = {"format": "c110454-nine-selected-semantic-proof-v1",
         "manifest_sha256": sha(manifest_path), "semantic_index_sha256": sha(index_path),
         "selected_case_count": 9, "rail_distance_ft": rail,
         "pinned_stage_chain_passed": True, "original_native_accepted": False,
         "canonical_delivery_selected": True,
         "raw_frozen_assignment_error": "Assignment lacks exact law text",
         "in_memory_law_key_adapter_passed": True}
output = HERE / "update041-selected-semantic-proof.json"
output.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({"proof_sha256": sha(output), **proof}))
