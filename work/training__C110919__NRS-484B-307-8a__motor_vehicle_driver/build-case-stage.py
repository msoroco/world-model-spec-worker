"""Build the source-linked C110919 case stage without claiming judgment sweeps complete."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "proposals/cases.json"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = read(HERE / "case-plan.json")
    binding = read(HERE / "proposals/bindings.json")
    template = read(HERE / "proposals/template.json")
    old = read(OUT)
    prior_descriptions = {case["case_id"]: case["recording_description"]
                          for case in old["cases"] if case["target_type"] != "baseline"}
    manifest_path = HERE / "update038-ten-case-probe-manifest.json"
    manifest = read(manifest_path)
    if manifest.get("case_plan_sha256") != sha(HERE / "case-plan.json"):
        raise ValueError("Final-hash manifest does not bind current case plan")
    descriptions = {}
    for entry in manifest["cases"]:
        construction_path = HERE / entry["construction"]
        if entry.get("kind") != "delivery" or sha(construction_path) != entry["construction_sha256"]:
            raise ValueError("Exact construction hash changed")
        description = read(construction_path)["recording_description"]
        if (entry["case_id"] not in prior_descriptions or
                {channel["name"] for channel in description["channels"]} !=
                {channel["name"] for channel in prior_descriptions[entry["case_id"]]["channels"]}):
            raise ValueError("Required recording channels changed")
        descriptions[entry["case_id"]] = description
    ids = [case["case_id"] for case in plan["cases"]]
    if len(ids) != len(set(ids)) or len(ids) != 10 or set(ids) != set(descriptions):
        raise ValueError("Current ten-case plan or recording descriptions differ")
    names = {item["name"]: item["kind"] for item in binding["variable_parameters"]}
    if set(names) != {"halt_before_nearest_boundary",
                      "halt_before_intersection_when_no_crosswalk_sign_or_marking",
                      "remain_stopped_until_green", "pedestrian_conflict_response",
                      "signal_directed_other_traffic_response"}:
        raise ValueError("Bound comparison variables changed")
    pairs = {}
    for comparison in plan["comparisons"]:
        if len(comparison["case_ids"]) != 2 or len(comparison["deliberate_differences"]) != 1:
            raise ValueError("Comparison is not an isolated pair")
        for ident in comparison["case_ids"]:
            if ident in pairs:
                raise ValueError("Case occurs in more than one comparison")
            pairs[ident] = comparison
    if set(pairs) != set(ids) or len(plan["comparisons"]) != 5:
        raise ValueError("Comparison plan does not cover ten cases")

    def assignments(row=None):
        active = row["comparison_variable"] if row else None
        output = {}
        for name, kind in names.items():
            value = None if kind == "subject_behavior" else (
                "yield_wait" if name == "pedestrian_conflict_response" else
                "traffic_yield_wait")
            if row and name == active and kind == "controller":
                value = row["requested_setting"]
            entry = {"kind": kind, "value": value}
            if kind == "subject_behavior":
                entry["note"] = "Observe original motion; no authored behavior value"
                if row and name == active:
                    entry["requested_target"] = row["requested_setting"]
            output[name] = entry
        return output

    judgments = template["structure"]["judgment_calls_needed"]
    if [item["phrase"] for item in judgments] != [
            "situated on the extreme right of the highway", "yield the right-of-way"]:
        raise ValueError("Source judgment phrases or order changed")
    phrases = [item["phrase"] for item in judgments]
    cases = [{"case_id": HERE.name + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Neutral definition for fixed C110919 right-turn context; not selected for delivery",
              "variable_assignments": assignments(),
              "recording_description": deepcopy(descriptions[ids[0]]),
              "unresolved_judgment_calls": phrases}]
    for row in plan["cases"]:
        ident = row["case_id"]
        pair = pairs[ident]
        variable = pair["deliberate_differences"][0]
        if variable != row["comparison_variable"]:
            raise ValueError("Case and comparison variable differ: " + ident)
        cases.append({"case_id": ident, "target_law_id": row["target_law_id"],
                      "target_type": "boundary_probe",
                      "rationale": row["case_description"] + " Original activation and judgment remain unverified.",
                      "paired_probe_id": pair["comparison_id"],
                      "deliberate_differences": [variable],
                      "probe": {"primary_variable": variable,
                                "comparison_or_standard": "Controlled physical branch; legal judgment unresolved",
                                "target_value_or_branch": row["requested_setting"]},
                      "variable_assignments": assignments(row),
                      "recording_description": deepcopy(descriptions[ident]),
                      "unresolved_judgment_calls": phrases})
    sweeps = []
    for slug, judgment in zip(("extreme-right", "right-of-way"), judgments):
        sweeps.append({"sweep_id": "C110919-" + slug,
                       "target_law_id": template["law_id"],
                       "judgment_refs": [{"phrase": judgment["phrase"],
                                          "note": judgment["note"]}],
                       "status": "incomplete",
                       "rationale": "Physical coverage plan for an unresolved statutory judgment; no legal cutoff or label",
                       "missing_inputs": [
                           "A documented scalar controller/world_setup axis mapped to a canonical measured binding parameter",
                           "Verified physical range, spacing and feasibility evidence from the C110919 construction and capture profile",
                           "Source-complete recording description for the judgment's original observations and context"]})
    stage = {"format": "worker-draft-proposals-v1", "cell_id": plan["cell_id"],
             "actor": binding["actor"], "status": "draft", "cases": cases,
             "sweep_specs": sweeps}
    from sys import path
    path.insert(0, str(HERE.parents[1] / "runtime/pipeline"))
    from scenario_pipeline.batch_pipeline.sweeps import validate_spec
    for spec in sweeps:
        validate_spec(spec)
    OUT.write_text(json.dumps(stage, indent=2) + "\n")
    print(json.dumps({"ordinary_cases": len(cases), "planned_delivery_cases": 10,
                      "explicitly_incomplete_judgment_sweeps": len(sweeps),
                      "sha256": sha(OUT)}))


if __name__ == "__main__":
    main()
