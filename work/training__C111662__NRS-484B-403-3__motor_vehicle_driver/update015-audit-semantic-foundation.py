"""Independently recheck semantic stage sources and meaningful rejections."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime/pipeline/scenario_pipeline"))
from batch_pipeline import stages  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rejected(stage, value, inputs):
    try:
        stages.validate(stage, value, inputs)
    except ValueError:
        return True
    raise ValueError("Invalid semantic stage was accepted: " + stage)


def run():
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    proof = json.loads((ROOT / "proposals/semantic-foundation-proof.json").read_text())
    if proof["assignment_sha256"] != sha(REPO / "inputs" / ROOT.name / "assignment.json"):
        raise ValueError("Frozen semantic assignment changed")
    refs = proof["references"]
    values = {}
    for stage, ref in refs.items():
        references = ref if isinstance(ref, list) else [ref]
        values[stage] = []
        for item in references:
            path = ROOT / item["path"]
            if sha(path) != item["sha256"]:
                raise ValueError("Semantic proposal hash changed: " + stage)
            values[stage].append(json.loads(path.read_text()))
    law = assignment["law_record"]
    request = {"cell": assignment["cell"], "actor": assignment["actor"]}
    common = {"request": request, "law_records": {assignment["law_id"]: law},
              "dependencies": []}
    for name in ("relevance", "relevance_batch"):
        stages.validate(name, deepcopy(values[name][0]), common)
    if values["relevance"] != values["relevance_batch"]:
        raise ValueError("Relevance stage proposals disagree")
    rules = json.loads((stages.ROOT / "data/canonical_parameter_aliases.json").read_text())
    template = values["template"][0]
    template_input = {"request": {"law_id": assignment["law_id"],
                                  "actor": assignment["actor"]},
                      "law_record": law, "canonical_parameter_rules": rules,
                      "dependencies": []}
    stages.validate("template", deepcopy(template), template_input)
    judgment = values["judgment_observables"][0]
    judgment_input = {"request": {"template_id": template["template_id"],
                                  "phrase": judgment["phrase"], "note": judgment["note"]},
                      "dependencies": []}
    stages.validate("judgment_observables", deepcopy(judgment), judgment_input)
    binding = values["bindings"][0]
    binding_input = {"request": dict(request, template_ids=[template["template_id"]]),
                     "canonical_parameter_rules": rules, "dependencies": [template]}
    stages.validate("bindings", deepcopy(binding), binding_input)
    if binding["law_refs"] or binding["context_refs"][0]["missing_guards"] != [
            "business_district_building_use_and_boundaries"]:
        raise ValueError("Business-district guard was activated or changed")
    wrong_quote = deepcopy(template)
    wrong_quote["quote"] = "Unrelated U-turn clause"
    rejected("template", wrong_quote, template_input)
    invented_threshold = deepcopy(judgment)
    invented_threshold["observable_requirements"]["observables"][0]["threshold"] = 3
    rejected("judgment_observables", invented_threshold, judgment_input)
    missing_guard = deepcopy(binding)
    missing_guard["context_refs"][0]["missing_guards"] = []
    rejected("bindings", missing_guard, binding_input)
    return {"format": "c111662-semantic-foundation-audit-v1",
            "assignment_id": ROOT.name, "passed": True,
            "positive_stage_count": 5,
            "negative_rejections": ["wrong_law_quote", "invented_judgment_threshold",
                                    "missing_business_district_guard"],
            "source_proof_sha256": sha(ROOT / "proposals/semantic-foundation-proof.json"),
            "scope": "draft conditional semantic stages; cases and semantic index remain incomplete"}


if __name__ == "__main__":
    result = run()
    path = ROOT / "proposals/semantic-foundation-audit.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "negative_count": len(result["negative_rejections"]),
                      "audit_sha256": sha(path)}))
