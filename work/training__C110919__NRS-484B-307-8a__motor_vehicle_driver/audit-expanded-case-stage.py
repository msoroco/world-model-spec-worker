"""Independent audit of ten ordinary probes and five expanded timing probes."""
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "runtime/pipeline"))
from scenario_pipeline.batch_pipeline.validation import coverage, recording_description
from scenario_pipeline.batch_pipeline.sweeps import validate_spec


def read(name):
    return json.loads((HERE / name).read_text())


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(stage):
    plan = read("case-plan.json")
    binding = read("proposals/bindings.json")
    template = read("proposals/template.json")
    for judgment in template["structure"]["judgment_calls_needed"]:
        name = ("judgment-right-of-way.json" if judgment["phrase"] == "yield the right-of-way"
                else "judgment-extreme-right.json")
        evidence = read("proposals/" + name)
        require(evidence["phrase"] == judgment["phrase"], "Judgment source differs")
        judgment["observable_requirements"] = evidence["observable_requirements"]
    ten_manifest = read("update038-ten-case-probe-manifest.json")
    sweep_manifest = read("update041-traffic-timing-sweep-manifest.json")
    require(stage["status"] == "draft" and stage.get("sweeps_expanded") is True and
            ten_manifest["case_plan_sha256"] == sha("case-plan.json") and
            sweep_manifest["stage_sha256"] == sha("proposals/right-of-way-sweep-candidate.json"),
            "Current draft stage or source manifest differs")
    ordinary = [case for case in stage["cases"] if case["target_type"] != "judgment_sweep"]
    timing = [case for case in stage["cases"] if case.get("sweep_id") == "C110919-right-of-way"]
    require(len(ordinary) == 11 and len(timing) == 5 and
            [case["case_id"] for case in ordinary[1:]] ==
            [row["case_id"] for row in plan["cases"]],
            "Ten ordinary or five timing cases missing")
    kinds = {item["name"]: item["kind"] for item in binding["variable_parameters"]}
    require({"traffic_launch_frame", "ego_entry_relative_to_signal_directed_traffic"} <= set(kinds),
            "Timing controller or observed binding absent")
    for case in stage["cases"]:
        require(set(case["variable_assignments"]) == set(kinds),
                "Case lacks full canonical variable assignments")
        require(all(entry["kind"] == kinds[name] and
                    (entry["value"] is None if entry["kind"] == "subject_behavior" else True)
                    for name, entry in case["variable_assignments"].items()),
                "Observed behavior was authored or parameter kind changed")
        recording_description(case["recording_description"])
    by_id = {c["case_id"]: c for c in ordinary}
    for pair in plan["comparisons"]:
        left, right = (by_id[x] for x in pair["case_ids"])
        variable = pair["deliberate_differences"][0]
        require(left["paired_probe_id"] == right["paired_probe_id"] == pair["comparison_id"] and
                left["recording_description"] == right["recording_description"] and
                all(left["variable_assignments"][name] == right["variable_assignments"][name]
                    for name in kinds if name != variable),
                "Ordinary controlled pair changed held facts")
    spec = next(x for x in stage["sweep_specs"] if x["sweep_id"] == "C110919-right-of-way")
    other = next(x for x in stage["sweep_specs"] if x["sweep_id"] == "C110919-extreme-right")
    validate_spec(spec)
    validate_spec(other)
    require(spec["status"] == "complete" and other["status"] == "incomplete" and
            spec["planned_case_count"] == 5 and
            [c["case_id"] for c in timing] == spec["selection_order"] and
            all(c["sweep_spec_version"] == spec["spec_version"] for c in timing),
            "Frozen timing sweep or incomplete extreme-right status differs")
    for case in timing:
        require(case["variable_assignments"]["traffic_launch_frame"]["value"] ==
                case["sweep_point"]["traffic_launch_frame"] and
                case["variable_assignments"]["ego_entry_relative_to_signal_directed_traffic"]["value"] is None and
                case["recording_description"] == spec["recording_description"],
                "Authored sweep command and measured value were conflated")
    coverage(stage["cases"], binding, [template], stage["sweep_specs"])
    return {"format": "c110919-expanded-stage-source-audit-v1",
            "case_plan_sha256": sha("case-plan.json"),
            "stage_sha256": sha("proposals/cases.json"),
            "binding_sha256": sha("proposals/bindings.json"),
            "ordinary_cases": 10, "timing_sweep_cases": 5,
            "complete_sweep_specs": 1, "incomplete_sweep_specs": 1,
            "canonical_delivery_selected": False}


def main():
    stage = read("proposals/cases.json")
    outcome = audit(stage)
    negatives = {}
    for name in ("missing_timing_case", "fabricated_observed_value",
                 "altered_sweep_point", "missing_survey_context"):
        changed = copy.deepcopy(stage)
        if name == "missing_timing_case":
            changed["cases"].pop()
        elif name == "fabricated_observed_value":
            changed["cases"][-1]["variable_assignments"]["ego_entry_relative_to_signal_directed_traffic"]["value"] = 1.0
        elif name == "altered_sweep_point":
            changed["cases"][-1]["sweep_point"]["traffic_launch_frame"] = 999
        else:
            changed["sweep_specs"][1]["recording_description"]["context_inputs"] = [
                x for x in changed["sweep_specs"][1]["recording_description"]["context_inputs"]
                if x["name"] != "surveyed_C110919_intersection"]
        try:
            audit(changed)
        except ValueError as error:
            negatives[name] = str(error)
        else:
            raise AssertionError("Damaged stage accepted: " + name)
    outcome["negative_rejections"] = negatives
    path = HERE / "update049-expanded-case-stage-audit.json"
    path.write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps({"ordinary_cases": 10, "timing_sweep_cases": 5,
                      "negative_rejections": len(negatives), "audit_sha256": sha(path.name)}))


if __name__ == "__main__":
    main()
