"""Write source-bound draft semantic proposals for the exact speed cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
LAW = "LVMC-11-16-060"
ACTOR = "motor_vehicle_driver"
TEXT = "The prima facie speed limit is twenty-five miles per hour on all streets and highways unless a different speed limit is posted as set forth in this Title."
TEMPLATE = LAW + "@" + ACTOR


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    source = json.loads((HERE.parents[1] / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    text = source["law"]["text"]
    assert TEXT in text
    desc = json.loads((HERE / "draft-exact/probe_1/primary/construction.json").read_text())["recording_description"]
    relevance = {"cell_id": "C179819", "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": TEXT, "applies_to": [ACTOR],
            "relevance_type": "specific_match", "confidence": "high",
            "notes": "Exact speed law applies to travel on a street or highway; original street and sign authority need review."}],
        "borderline_excluded": []}
    refs = {}
    refs["relevance_batch"] = write(HERE / "proposals/relevance-batch.json", relevance)
    refs["relevance"] = write(HERE / "proposals/relevance.json", relevance)
    judgments = [{"phrase": "prima facie", "note": "Measured speed and governing sign do not settle legal status."},
                 {"phrase": "posted as set forth in this Title", "note": "Original applicable sign and legal posting authority require independent review."}]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "status": "draft",
        "quote": TEXT, "structure": {
            "activation": {"description": "Travel on a street or highway.", "source_clause": "on all streets and highways"},
            "obligation": {"description": "Measure speed against the prima facie default reference, subject to an applicable different posted limit; reserve legal status.",
                "type": "must", "source_clause": "The prima facie speed limit is twenty-five miles per hour",
                "numeric_conditions": [{"variable": "ego_speed", "operator": "<=", "value": 25, "unit": "mph"}]},
            "exceptions": [{"source_clause": "unless a different speed limit is posted as set forth in this Title",
                "trigger": "A different posted limit applies to this street and route.",
                "effect": "Use the reviewed posted reference for comparison.",
                "replacement_obligation": "Measure speed against the reviewed different posted limit, without assigning a legal verdict."}],
            "timing": {"description": "Use the original synchronized speed and governing-sign intervals."},
            "judgment_calls_needed": judgments},
        "parameter_refs": [{"name": "ego_speed", "kind": "subject_behavior", "range_or_domain": "observed mph from original Native velocity"},
            {"name": "posted_limit_mph", "kind": "world_setup", "range_or_domain": "no different applicable sign or source-reviewed posted mph"}]}
    refs["template"] = write(HERE / "proposals/template.json", template)
    observed = []
    for index, judgment in enumerate(judgments, 1):
        names = (["kin.speed", "st.roadway", "dev.governs"] if index == 1 else
                 ["dev.speed_limit_sign", "dev.governs", "st.roadway"])
        req = {"observables": [{"name": n, "unit": "m/s" if n == "kin.speed" else "structured",
                    "description": "Original synchronized source stream for " + n} for n in names],
            "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
            "recording_needs": [{"name": n, "unit": "m/s" if n == "kin.speed" else "structured",
                "description": "Retain original source and time join for " + n} for n in names],
            "limitations": ["Original public street, sign face, applicability and legal status require independent review."]}
        observed.append(write(HERE / ("proposals/judgment-%d.json" % index),
            {"template_id": TEMPLATE, "phrase": judgment["phrase"], "note": judgment["note"],
             "status": "draft", "observable_requirements": req}))
    refs["judgment_observables"] = observed
    binding = {"cell_id": "C179819", "actor": ACTOR, "status": "draft", "established_contexts": [],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}], "context_refs": [],
        "fixed_parameters": [{"name": "road_context", "value": "paved road travel", "rationale": "Frozen catalog cell."}],
        "variable_parameters": [
            {"name": "ego_speed", "kind": "subject_behavior", "range_or_domain": "observed mph; never predetermined", "used_by_laws": [LAW]},
            {"name": "commanded_approach_speed", "kind": "controller", "range_or_domain": "20, 25, or 30 mph request expressed in m/s", "used_by_laws": [LAW]},
            {"name": "posted_limit_mph", "kind": "world_setup", "range_or_domain": "none or authored 35 mph different sign, subject to original review", "used_by_laws": [LAW]}]}
    refs["bindings"] = write(HERE / "proposals/bindings.json", binding)
    cases = [{"case_id": ASSIGNMENT + "__baseline", "target_law_id": None, "target_type": "baseline",
        "rationale": "Shared frozen paved-road context before a speed request.",
        "variable_assignments": {"ego_speed": {"kind": "subject_behavior", "value": None},
            "commanded_approach_speed": {"kind": "controller", "value": None},
            "posted_limit_mph": {"kind": "world_setup", "value": None}},
        "unresolved_judgment_calls": [j["phrase"] for j in judgments], "recording_description": desc}]
    for suffix, mph, posted in (("probe_1", 20, None), ("probe_2", 25, None),
                                ("probe_3", 30, None), ("posted_35", 30, 35)):
        benchmark = suffix != "posted_35"
        case = {"case_id": ASSIGNMENT + "__" + suffix, "target_law_id": LAW,
            "target_type": "boundary_probe" if benchmark else "judgment_sweep",
            "rationale": "Observe original speed and governing-sign context, without a legal outcome label.",
            "paired_probe_id": "default_25" if benchmark else "posted_35_comparison",
            "deliberate_differences": ["commanded_approach_speed"] if benchmark else ["posted_limit_mph"],
            "variable_assignments": {"ego_speed": {"kind": "subject_behavior", "value": None},
                "commanded_approach_speed": {"kind": "controller", "value": round(mph * 0.44704, 6)},
                "posted_limit_mph": {"kind": "world_setup", "value": posted}},
            "unresolved_judgment_calls": [j["phrase"] for j in judgments],
            "recording_description": desc,
            "probe": {"primary_variable": "ego_speed" if benchmark else "posted_limit_mph",
                "comparison_or_standard": "prima facie 25 mph measurement reference" if benchmark else "different posted limit branch",
                "target_value_or_branch": mph if benchmark else "posted_35"}}
        if benchmark:
            case["probe"].update({"threshold_ref": "obligation.numeric_conditions[0]",
                "operator": "<=", "unit": "mph", "test_value": mph})
            case["epsilon_used"] = {"value": 5, "unit": "mph",
                "rationale": "Physical speed separation for recording; no legal tolerance."}
        cases.append(case)
    specs = [{"sweep_id": "prima-facie-interpretation-review", "target_law_id": LAW,
        "judgment_refs": [judgments[0]], "status": "incomplete",
        "rationale": "Selected speed probes preserve measured evidence while legal interpretation remains open.",
        "missing_inputs": ["Independent legal interpretation of prima facie status from original evidence."]},
        {"sweep_id": "posted-authority-review", "target_law_id": LAW,
        "judgment_refs": [judgments[1]], "status": "incomplete",
        "rationale": "Selected posted case preserves sign and road sources while official posting authority remains open.",
        "missing_inputs": ["Independent original sign face, road applicability and posting-authority review."]}]
    refs["cases"] = write(HERE / "proposals/cases.json", {"cell_id": "C179819", "actor": ACTOR,
        "status": "draft", "sweep_specs": specs, "sweeps_expanded": True, "cases": cases})
    write(HERE / "proposals/semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ASSIGNMENT, "stages": refs})


if __name__ == "__main__":
    main()
