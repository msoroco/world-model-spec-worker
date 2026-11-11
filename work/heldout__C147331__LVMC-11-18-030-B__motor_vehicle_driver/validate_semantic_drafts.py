"""Validate authored source-bound semantic stages that precede case expansion."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from batch_pipeline import stages


def read(path):
    return json.loads(Path(path).read_text())


def main():
    assignment = read(ROOT / "inputs" / HERE.name / "assignment.json")
    folder = HERE / "proposals"
    law, cell, actor = assignment["law"], assignment["cell"], assignment["actor"]
    paths = {}
    for stage in ("relevance_batch", "relevance"):
        path = folder / (stage + ".json")
        stages.validate(stage, read(path), {"request": {"cell": cell, "actor": actor},
                                          "law_records": {assignment["law_id"]: law},
                                          "dependencies": []})
        paths[stage] = path
    rules = read(ROOT / "runtime/scenario_pipeline/data/canonical_parameter_aliases.json")
    template_path = folder / "template.json"
    template = read(template_path)
    stages.validate("template", template, {"request": {"law_id": assignment["law_id"],
                                                      "actor": actor}, "law_record": law,
                                            "canonical_parameter_rules": rules,
                                            "dependencies": []})
    paths["template"] = template_path
    for name, judgment in zip(("judgment_passing", "judgment_turn"),
                              template["structure"]["judgment_calls_needed"]):
        path = folder / (name + ".json")
        stages.validate("judgment_observables", read(path), {
            "request": {"template_id": template["template_id"], **judgment},
            "dependencies": []})
        paths[name] = path
    binding_path = folder / "bindings.json"
    stages.validate("bindings", read(binding_path), {
        "request": {"cell": cell, "actor": actor,
                    "template_ids": [template["template_id"]]},
        "canonical_parameter_rules": rules, "dependencies": [template]})
    paths["bindings"] = binding_path
    receipt = {"format": "worker-partial-semantic-draft-validation",
               "assignment_id": HERE.name, "validated_stages": list(paths),
               "sources": {name: {"path": str(path.relative_to(HERE)),
                                   "sha256": sha256(path.read_bytes()).hexdigest()}
                           for name, path in paths.items()},
               "canonical_stage_chain_complete": False,
               "pending": "Canonical cases and full law judgment sweeps"}
    (HERE / "semantic-draft-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("Validated", len(paths), "semantic draft artifacts")


if __name__ == "__main__":
    main()
