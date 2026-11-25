"""Author the draft canonical stage chain for the exact two-case zone comparison."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / "proposals"
AID = HERE.name
LAW = "NRS-484B-110"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR


def save(name, data):
    path = PROPOSALS / name
    path.write_text(json.dumps(data, indent=2) + "\n")
    return {"path": "proposals/" + name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def assignment(name, kind, value, source):
    return {"kind": kind, "value": value, "unit": "structured", "source": source}


def build():
    original = json.loads((HERE / "../../inputs" / AID / "assignment.json").resolve().read_text())
    law = original["law"]
    quote = law["text"]
    recording = json.loads((PROPOSALS / "cases.json").read_text())["cases"][0]["recording_description"]
    relevance = {"cell_id": "C10374", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
                                    "relevance_type": "direct", "confidence": "high",
                                    "notes": "Frozen safety-zone travel cell; original designation remains to be reviewed."}],
                 "borderline_excluded": []}
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "status": "draft", "quote": quote,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "A vehicle is driven in the observed roadway setting.",
                                             "numeric_conditions": []},
                              "obligation": {"type": "must_not", "description": "Drive through or within a safety zone.",
                                             "numeric_conditions": []},
                              "exceptions": [],
                              "timing": {"description": "At any time during the original observed travel episode.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": []},
                "parameter_refs": [{"name": "safety_zone_designation", "kind": "world_setup",
                                    "range_or_domain": "original map/road authority and source-bound human review"},
                                   {"name": "vehicle_zone_overlap", "kind": "subject_behavior",
                                    "range_or_domain": "original moving body polygon versus designated zone"}]}
    bindings = {"cell_id": "C10374", "actor": ACTOR, "status": "draft",
                "established_contexts": ["Frozen alley/safety-zone cell is planning context, not original physical designation."],
                "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}], "context_refs": [],
                "fixed_parameters": [],
                "variable_parameters": [
                    {"name": "safety_zone_designation", "kind": "world_setup",
                     "range_or_domain": "official designation unverified until original review", "used_by_laws": [LAW]},
                    {"name": "vehicle_zone_overlap", "kind": "subject_behavior",
                     "range_or_domain": "measured original moving body/zone intersection", "used_by_laws": [LAW]},
                    {"name": "route_request", "kind": "controller",
                     "range_or_domain": "route planned through zone or along controlled outside path", "used_by_laws": [LAW]},
                    {"name": "commanded_approach_speed", "kind": "controller",
                     "range_or_domain": "physical route feasibility only; no legal speed boundary", "used_by_laws": [LAW]},
                ]}
    var = {
        "safety_zone_designation": assignment("safety_zone_designation", "world_setup", None,
                                               "original designation and map review pending"),
        "vehicle_zone_overlap": assignment("vehicle_zone_overlap", "subject_behavior", None,
                                           "original body polygon and zone geometry"),
        "route_request": assignment("route_request", "controller", None,
                                    "planned route; observed movement remains separate"),
        "commanded_approach_speed": assignment("commanded_approach_speed", "controller", 8.0,
                                               "requested route speed in m/s; not a legal threshold"),
    }
    baseline = {"case_id": AID + "__baseline", "target_law_id": None, "target_type": "baseline",
                "rationale": "Shared designated-zone question, body and four-view source contract without an outcome claim.",
                "variable_assignments": var, "unresolved_judgment_calls": [],
                "recording_description": recording}
    cases = [baseline]
    for suffix, through, target in (("a", True, "violating_attempt"), ("b", False, "compliant_attempt")):
        case = AID + "__selected_c5852cfd__condition_" + suffix
        values = json.loads(json.dumps(var))
        values["route_request"]["value"] = "through_zone" if through else "outside_zone"
        cases.append({"case_id": case, "target_law_id": LAW, "target_type": target,
                      "rationale": "Controlled planned route; original designation and body overlap require physical review.",
                      "variable_assignments": values, "unresolved_judgment_calls": [],
                      "recording_description": recording,
                      "paired_probe_id": AID + "__selected_c5852cfd__comparison",
                      "deliberate_differences": ["route_request"],
                      "probe": {"primary_variable": "route_request",
                                "comparison_or_standard": "paired outside-zone versus through-zone requested route",
                                "target_value_or_branch": values["route_request"]["value"]}})
    proposed = {"cell_id": "C10374", "actor": ACTOR, "status": "draft", "cases": cases,
                "sweep_specs": [], "sweeps_expanded": True}
    references = {"relevance_batch": save("relevance-batch.json", relevance),
                  "relevance": save("relevance.json", relevance),
                  "template": save("template.json", template),
                  "judgment_observables": [],
                  "bindings": save("bindings.json", bindings),
                  "cases": save("cases.json", proposed)}
    save("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": AID,
                                 "stages": references})


if __name__ == "__main__":
    build()
