"""Independently check the ten-case draft against the current source plan."""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline"))
from scenario_pipeline.batch_pipeline.sweeps import expand_sweeps, validate_spec
from scenario_pipeline.batch_pipeline.validation import coverage, recording_description


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(name):
    return json.loads((HERE / name).read_text())


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def audit(stage):
    plan = read("case-plan.json")
    binding = read("proposals/bindings.json")
    template = read("proposals/template.json")
    manifest = read("update038-ten-case-probe-manifest.json")
    require(manifest["case_plan_sha256"] == sha("case-plan.json"),
            "Case plan changed after final-hash construction")
    require(stage.get("cell_id") == plan["cell_id"] and
            stage.get("actor") == plan["actor"] and stage.get("status") == "draft",
            "Case stage identity or draft status changed")
    cases = stage["cases"]
    require(len(cases) == 11 and cases[0]["target_type"] == "baseline" and
            [row["case_id"] for row in cases[1:]] ==
            [row["case_id"] for row in plan["cases"]],
            "Baseline or exact ten-case inventory changed")
    variable_kinds = {row["name"]: row["kind"] for row in binding["variable_parameters"]}
    phrases = {j["phrase"] for j in template["structure"]["judgment_calls_needed"]}
    by_id = {case["case_id"]: case for case in cases}
    for case in cases:
        recording_description(case["recording_description"])
        require(set(case["variable_assignments"]) == set(variable_kinds) and
                set(case["unresolved_judgment_calls"]) == phrases,
                "Bound variable or unresolved judgment missing")
        for name, kind in variable_kinds.items():
            assigned = case["variable_assignments"][name]
            require(assigned["kind"] == kind and
                    (kind != "subject_behavior" or assigned["value"] is None),
                    "Observed behavior was authored as a value")
    for plan_case in plan["cases"]:
        case = by_id[plan_case["case_id"]]
        exact = next(entry for entry in manifest["cases"]
                     if entry["case_id"] == case["case_id"])
        construction_path = exact["construction"]
        require(sha(construction_path) == exact["construction_sha256"] and
                read(construction_path)["recording_description"] ==
                case["recording_description"],
                "Case recording contract differs from exact tested construction")
        require(case["target_type"] == "boundary_probe" and
                case["target_law_id"] == plan["law_id"] and
                case["probe"]["primary_variable"] == plan_case["comparison_variable"] and
                case["probe"]["target_value_or_branch"] == plan_case["requested_setting"],
                "Case target or source comparison variable changed")
    for pair in plan["comparisons"]:
        left, right = (by_id[ident] for ident in pair["case_ids"])
        variable = pair["deliberate_differences"][0]
        require(left["paired_probe_id"] == right["paired_probe_id"] ==
                pair["comparison_id"] and
                left["deliberate_differences"] == right["deliberate_differences"] ==
                [variable] and
                left["recording_description"] == right["recording_description"] and
                all(left["variable_assignments"][name] ==
                    right["variable_assignments"][name]
                    for name in variable_kinds if name != variable),
                "Pair changed a held variable, recording or comparison identity")
        active_left, active_right = (case["variable_assignments"][variable]
                                     for case in (left, right))
        branch = (lambda item: item["value"] if item["kind"] == "controller"
                  else item.get("requested_target"))
        require(branch(active_left) != branch(active_right) and
                branch(active_left) == left["probe"]["target_value_or_branch"] and
                branch(active_right) == right["probe"]["target_value_or_branch"],
                "Pair lacks a distinct requested branch")
    specs = stage["sweep_specs"]
    require(len(specs) == len(phrases) == 2 and
            {spec["judgment_refs"][0]["phrase"] for spec in specs} == phrases,
            "Judgment sweep phrase coverage differs")
    for spec in specs:
        validate_spec(spec)
        require(spec["status"] == "incomplete" and spec["missing_inputs"],
                "Unsupported sweep was declared complete")
    normalized = copy.deepcopy(stage)
    expand_sweeps(normalized, [template], binding)
    coverage(normalized["cases"], binding, [template], normalized["sweep_specs"])
    return {"format": "c110919-case-stage-source-audit-v1",
            "case_plan_sha256": sha("case-plan.json"),
            "case_stage_sha256": sha("proposals/cases.json"),
            "cases_checked": 10, "paired_comparisons_checked": 5,
            "judgment_sweep_plans_checked": 2, "complete_judgment_sweeps": 0,
            "canonical_selected": False}


def main():
    stage = read("proposals/cases.json")
    outcome = audit(stage)
    negatives = {}
    for name in ("missing_case", "fabricated_behavior", "held_context_changed",
                 "false_sweep_complete"):
        changed = copy.deepcopy(stage)
        if name == "missing_case":
            changed["cases"].pop()
        elif name == "fabricated_behavior":
            changed["cases"][1]["variable_assignments"]["halt_before_nearest_boundary"]["value"] = True
        elif name == "held_context_changed":
            changed["cases"][2]["variable_assignments"]["pedestrian_conflict_response"]["value"] = "yield_conflict_entry"
        else:
            changed["sweep_specs"][0]["status"] = "complete"
        try:
            audit(changed)
        except ValueError as error:
            negatives[name] = str(error)
        else:
            raise AssertionError("Damaged case stage passed: " + name)
    outcome["negative_rejections"] = negatives
    target = HERE / "update039-case-stage-audit.json"
    target.write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps({"cases_checked": 10, "comparisons_checked": 5,
                      "incomplete_sweeps": 2,
                      "negative_rejections": len(negatives),
                      "audit_sha256": sha(target.name)}))


if __name__ == "__main__":
    main()
