"""Independent source and cross-stage check of C110919 draft semantic stages."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INDEX = HERE / "proposals/semantic-index.json"
SOURCE = ROOT / "inputs" / HERE.name / "assignment.json"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(index, *, template_override=None):
    source = read(SOURCE)
    plan = read(HERE / "case-plan.json")
    require(index["assignment_id"] == HERE.name and
            index["format"] == "worker-semantic-delivery" and
            index["status"] == "draft_not_delivery_selected", "Semantic identity or status changed")
    stages = index["stages"]
    def stage(name):
        binding = stages[name]
        path = HERE / binding["path"]
        require(path.is_file() and sha(path) == binding["sha256"], "Semantic stage hash changed: " + name)
        return read(path)
    relevance_batch = stage("relevance_batch")
    relevance = stage("relevance")
    template = stage("template") if template_override is None else template_override
    bindings = stage("bindings")
    cases = stage("cases")
    require(relevance_batch == relevance and relevance["cell_id"] == source["cell_id"] and
            relevance["actor"] == source["actor"] and
            relevance["relevant_laws"][0]["quote"] == source["law_record"]["text"] and
            template["quote"] == source["law_record"]["text"] and
            template["law_id"] == source["law_id"] and
            template["actor"] == source["actor"],
            "Frozen law or relevance source changed")
    require([row["case_id"] for row in cases["cases"] if row["target_type"] != "baseline"] ==
            [row["case_id"] for row in plan["cases"]] and len(cases["cases"]) == 11 and
            len(plan["comparisons"]) == 5, "Semantic ten-case inventory changed")
    require(cases.get("cell_id") == source["cell_id"] and
            cases.get("actor") == source["actor"] and
            len(cases.get("sweep_specs", [])) == 2 and
            all(spec.get("status") == "incomplete" and spec.get("missing_inputs")
                for spec in cases["sweep_specs"]),
            "Judgment sweep gaps or case-stage identity changed")
    comparison_vars = {difference for item in plan["comparisons"]
                       for difference in item["deliberate_differences"]}
    require(comparison_vars <= {row["name"] for row in bindings["variable_parameters"]} and
            bindings["law_refs"][0]["template_id"] == template["template_id"],
            "Semantic comparison variables or template binding changed")
    exceptions = {row["name"]: row for row in template["structure"]["exceptions"]}
    require("post_stop_right_turn" in exceptions and
            exceptions["paragraph_d_reference"]["status"] ==
            "operative_text_not_in_frozen_law_record; preserve unresolved description" and
            template["structure"]["obligation"]["numeric_conditions"] == [] and
            template["structure"]["timing"]["numeric_conditions"] == [],
            "Exception uncertainty or legal numeric threshold changed")
    judgments = stages["judgment_observables"]
    require(len(judgments) == 2, "Judgment stages incomplete")
    phrases = set()
    for binding in judgments:
        path = HERE / binding["path"]
        require(path.is_file() and sha(path) == binding["sha256"],
                "Judgment stage hash changed")
        item = read(path)
        require(item["template_id"] == template["template_id"] and
                item["observable_requirements"]["observables"] and
                item["observable_requirements"]["limitations"] and
                item["observable_requirements"]["sweep_dimensions"] and
                item["observable_requirements"]["landmarks"] == [],
                "Judgment source or limits missing")
        phrases.add(item["phrase"])
    require(phrases == {"situated on the extreme right of the highway",
                        "yield the right-of-way"}, "Judgment phrase coverage changed")
    return {"format": "c110919-semantic-stage-source-audit-v1",
            "assignment_source_sha256": sha(SOURCE),
            "semantic_index_sha256": sha(INDEX), "stages_checked": 7,
            "cases_checked": 10, "comparisons_checked": 5,
            "paragraph_d_status": "unresolved_frozen_text",
            "canonical_selected": False}


def main():
    index = read(INDEX)
    outcome = audit(index)
    negatives = {}
    changed = copy.deepcopy(index)
    changed["stages"]["cases"]["sha256"] = "0" * 64
    try:
        audit(changed)
    except ValueError as error:
        negatives["cases_hash_changed"] = str(error)
    else:
        raise AssertionError("Changed case stage hash was accepted")
    changed = copy.deepcopy(index)
    changed["stages"]["judgment_observables"].pop()
    try:
        audit(changed)
    except ValueError as error:
        negatives["judgment_missing"] = str(error)
    else:
        raise AssertionError("Missing judgment was accepted")
    template = read(HERE / index["stages"]["template"]["path"])
    template["structure"]["exceptions"][2]["status"] = "resolved"
    try:
        audit(index, template_override=template)
    except ValueError as error:
        negatives["paragraph_d_falsely_resolved"] = str(error)
    else:
        raise AssertionError("False paragraph (d) resolution was accepted")
    outcome["negative_rejections"] = negatives
    path = HERE / "update038-semantic-stage-audit.json"
    path.write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps({"stages_checked": 7, "cases_checked": 10,
                      "negative_rejections": len(negatives), "audit_sha256": sha(path),
                      "canonical_selected": False}))


if __name__ == "__main__":
    main()
