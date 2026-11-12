"""CPU proof of the draft semantic chain and its remaining coverage failure."""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "runtime/pipeline"), str(ROOT / "runtime/pipeline/scenario_pipeline")]
from batch_pipeline import stages  # noqa: E402
from scenario_pipeline.worker_exchange import semantic_delivery  # noqa: E402


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def error(assignment: dict, manifest: dict) -> str:
    try:
        semantic_delivery.validate(HERE, assignment, manifest)
    except ValueError as exc:
        return str(exc)
    raise AssertionError("Incomplete semantic chain unexpectedly validated")


assignment = read(ROOT / "inputs" / HERE.name / "assignment.json")
manifest = read(HERE / "execution-manifest.json")
index = read(HERE / "proposals/semantic-index.json")
law = assignment["law_record"]
request = {"cell": assignment["cell"], "actor": assignment["actor"]}
rules = read(stages.ROOT / "data/canonical_parameter_aliases.json")
loaded = {}
for stage in ("relevance_batch", "relevance", "template", "bindings", "cases"):
    ref = index["stages"][stage]
    path = HERE / ref["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == ref["sha256"]
    loaded[stage] = read(path)
assert loaded["relevance_batch"] == loaded["relevance"]
for stage in ("relevance_batch", "relevance"):
    stages.validate(stage, loaded[stage], {"request": request,
                    "law_records": {assignment["law_id"]: law}, "dependencies": []})
stages.validate("template", loaded["template"], {
    "request": {"law_id": assignment["law_id"], "actor": assignment["actor"]},
    "law_record": law, "canonical_parameter_rules": rules, "dependencies": []})
stages.validate("bindings", loaded["bindings"], {
    "request": dict(request, template_ids=[loaded["template"]["template_id"]]),
    "canonical_parameter_rules": rules, "dependencies": [loaded["template"]]})
selected = {c["case_id"]: c for c in loaded["cases"]["cases"] if c["target_type"] != "baseline"}
assert set(selected) == {entry["case_id"] for entry in manifest["cases"]}
for entry in manifest["cases"]:
    assert selected[entry["case_id"]]["recording_description"] == read(HERE / entry["construction"])["recording_description"]
rail = read(HERE / next(entry["construction"] for entry in manifest["cases"]
                        if entry["case_id"].endswith("__rail_reference")))
with tempfile.TemporaryDirectory() as temp:
    for name in ("geometry_base.py", "geometry_statutory.py"):
        (Path(temp) / name).write_text(next(f["content"] for f in rail["files"] if f["path"] == name))
    sys.path.insert(0, temp)
    geometry = importlib.import_module("geometry_statutory")
    for suffix in ("rail_reference", "rail_contrast", "oneway_absent", "oneway_present"):
        planned = selected[HERE.name + "__" + suffix]["variable_assignments"]["commanded_left_side_closest_distance_ft"]["value"]
        measured = geometry.check()["case_results"][suffix]["nearest_full_body_front_distance_m"] * 3.280839895
        assert abs(planned - measured) < 0.005, (suffix, planned, measured)
    sys.path.pop(0)
    del sys.modules["geometry_statutory"]
    del sys.modules["geometry_base"]
raw = error(assignment, manifest)
assert raw == "Assignment lacks exact law text", raw
adapted = dict(assignment, law=law)
coverage = error(adapted, manifest)
assert coverage.startswith("Missing or unlinked below/at/above coverage:"), coverage
proof = {
    "format": "c110454-semantic-draft-proof-v1",
    "assignment_id": HERE.name,
    "semantic_index_sha256": hashlib.sha256((HERE / "proposals/semantic-index.json").read_bytes()).hexdigest(),
    "passed": ["relevance_batch", "relevance", "template", "bindings", "all_source_hashes", "six_selected_case_ids_and_recording_descriptions", "four_sampled_full_body_distance_bindings"],
    "raw_frozen_assignment_validation": {"status": "fails", "reason": raw},
    "diagnostic_law_key_adapter_validation": {"status": "fails", "reason": coverage},
    "remaining_worker_work": "Author an at-100-foot selected boundary construction and prove it through the CPU chain without changing frozen inputs; then regenerate canonical cases and revalidate.",
}
out = HERE / "update033-semantic-proof.json"
out.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof, indent=2))
