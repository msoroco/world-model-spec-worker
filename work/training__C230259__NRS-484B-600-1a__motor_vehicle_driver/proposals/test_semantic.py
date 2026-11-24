"""Validate six draft stages against the pinned runtime stage contracts."""
import hashlib
import json
import os
from pathlib import Path
import sys

output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/nonexistent")).resolve()
if not output_root.is_relative_to((Path.cwd() / ".runtime-work").resolve()):
    raise SystemExit("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
sys.path.insert(0, str(Path("runtime/pipeline").resolve()))
from scenario_pipeline.batch_pipeline import stages

folder = Path(__file__).resolve().parent
assignment_id = folder.parent.name
assignment = json.loads((Path("inputs") / assignment_id / "assignment.json").read_text())


def load(name):
    return json.loads((folder / name).read_text())


request = {"cell": assignment["cell"], "actor": assignment["actor"]}
law_id = assignment["law_id"]
template_id = law_id + "@" + assignment["actor"]
common = {"request": request, "law_records": {law_id: assignment["law"]}, "dependencies": []}
rules = json.loads((stages.ROOT / "data/canonical_parameter_aliases.json").read_text())
inputs = {
    "relevance-batch.json": ("relevance_batch", common),
    "relevance.json": ("relevance", common),
    "template.json": ("template", {"request": {"law_id": law_id, "actor": assignment["actor"]},
                                  "law_record": assignment["law"], "canonical_parameter_rules": rules,
                                  "dependencies": []}),
}
template = load("template.json")
observable = load("judgment-observables.json")
inputs["judgment-observables.json"] = ("judgment_observables", {
    "request": {"template_id": template_id, "phrase": observable["phrase"], "note": observable["note"]},
    "dependencies": [],
})
binding = load("bindings.json")
inputs["bindings.json"] = ("bindings", {
    "request": dict(request, template_ids=[template_id]),
    "canonical_parameter_rules": rules, "dependencies": [template],
})
template["structure"]["judgment_calls_needed"][0]["observable_requirements"] = observable["observable_requirements"]
inputs["cases.json"] = ("cases", {
    "request": request, "dependencies": [binding], "templates": [template],
    "canonical_parameter_rules": rules, "judgment_completion_policy": {},
})

for name, (stage, stage_inputs) in inputs.items():
    stages.validate(stage, load(name), stage_inputs)
    print(name, "PASS")

proof = {
    "format": "semantic-stage-cpu-proof-v1", "assignment_id": assignment_id,
    "validated_stages": list(inputs), "all_stages_pass": True,
    "source_hashes": {name: hashlib.sha256((folder / name).read_bytes()).hexdigest() for name in inputs},
    "status": "draft_only",
    "remaining": "Execution manifest, exact selected cases, construction, saved-processing and audits are still required; accepted-recording equivalence is unresolved.",
}
(folder / "semantic-stage-cpu-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
