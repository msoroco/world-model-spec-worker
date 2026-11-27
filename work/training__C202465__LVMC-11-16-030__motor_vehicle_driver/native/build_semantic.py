"""Build draft canonical rail crossing stage proposals from the exact source."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
AID = WORK.name
ORIGINAL = json.loads((ROOT / "inputs" / AID / "assignment.json").read_text())
LAW = ORIGINAL["law_id"]
ACTOR = ORIGINAL["actor"]
TEMPLATE_ID = LAW + "@" + ACTOR
QUOTE = ORIGINAL["law"]["text"]


def write(name, value):
    path = WORK / "proposals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": str(path.relative_to(WORK)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    relevance = {"cell_id": ORIGINAL["cell_id"], "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": QUOTE, "applies_to": [ACTOR],
                                     "relevance_type": "specific_match", "confidence": "high",
                                     "notes": "Frozen rail-crossing cell; railway and exception identities still require original source review."}],
                 "borderline_excluded": []}
    rel = write("relevance.json", relevance)
    rel_batch = write("relevance_batch.json", relevance)
    judgments = [
        {"phrase": "clear and unobstructed view",
         "note": "actual subject sight of crossing and rail traffic requires original source review"},
        {"phrase": "clearly visible electrical or mechanical railway crossing signal device",
         "note": "device visibility and indication require original per-frame review"},
    ]
    template = {"template_id": TEMPLATE_ID, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": QUOTE,
                "structure": {
                    "activation": {"condition": "Motor vehicle traverses a grade crossing of a steam, electric or other motor railway after the stated approach visibility condition.",
                                   "numeric_conditions": []},
                    "obligation": {"type": "must", "description": "Observe the fifteen mile per hour prima facie traversal speed limit when the source conditions apply; legal classification remains external.",
                                   "numeric_conditions": [{"variable": "ego_speed", "operator": "<=",
                                                           "value": 15, "unit": "mph"}]},
                    "exceptions": [{"trigger": "human flagman on duty", "effect": "Section does not apply",
                                    "replacement_obligation": "none stated in this Section",
                                    "source_clause": "where a human flagman is on duty"},
                                   {"trigger": "clearly visible installed signal does not indicate immediate train or car approach",
                                    "effect": "Section does not apply",
                                    "replacement_obligation": "none stated in this Section",
                                    "source_clause": "clearly visible electrical or mechanical railway crossing signal device is installed but does not then indicate the immediate approach of a railway train or car"}],
                    "timing": {"description": "Assess crossing and railway traffic sight during the final one hundred feet of approach, and speed during traversal.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": judgments},
                "parameter_refs": [{"name": "ego_speed", "kind": "subject_behavior",
                                    "range_or_domain": "original traversal speed"},
                                   {"name": "commanded_approach_speed", "kind": "controller",
                                    "range_or_domain": "physical speed request in m/s"},
                                   {"name": "rail_sight_mode", "kind": "world_setup",
                                    "range_or_domain": "reviewed left, right and crossing sight geometry"},
                                   {"name": "rail_exception_state", "kind": "world_setup",
                                    "range_or_domain": "reviewed flagman duty and crossing device state"}]}
    template_ref = write("template.json", template)
    observable_refs = []
    for index, judgment in enumerate(judgments):
        name = "st.sight_distance" if index == 0 else "dev.railway_signal_or_gate"
        observable_refs.append(write("judgment-" + str(index) + ".json", {
            "template_id": TEMPLATE_ID, "phrase": judgment["phrase"], "note": judgment["note"],
            "status": "draft", "observable_requirements": {
                "observables": [{"name": name, "unit": "structured",
                                 "description": "Original Native frame and independent source review"}],
                "context_inputs": [{"name": "original_crossing_source_review", "unit": "structured",
                                    "description": "Original railway, jurisdiction, flagman and signal source identities"}],
                "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": name, "unit": "structured",
                                     "description": "Source-bound original frame observations for later independent judgment"}],
                "limitations": ["Collision rays and fixture flags cannot settle actual driver perception or legal exception meaning."]}}))
    binding = {"cell_id": ORIGINAL["cell_id"], "actor": ACTOR, "status": "draft",
               "established_contexts": [{"name": "at_grade_rail_crossing",
                                        "source": "frozen cell identity; original railway and traffic verification pending"}],
               "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": "ego_speed", "kind": "subject_behavior",
                                        "range_or_domain": "measured traversal speed; null until observed",
                                        "used_by_laws": [LAW]},
                                       {"name": "commanded_approach_speed", "kind": "controller",
                                        "range_or_domain": "speed target in m/s",
                                        "used_by_laws": [LAW]},
                                       {"name": "rail_sight_mode", "kind": "world_setup",
                                        "range_or_domain": "left/right/crossing occlusion source design",
                                        "used_by_laws": [LAW]},
                                       {"name": "rail_exception_state", "kind": "world_setup",
                                        "range_or_domain": "flagman and device source state",
                                        "used_by_laws": [LAW]}]}
    binding_ref = write("bindings.json", binding)
    selected = json.loads((WORK / "proposals/cases.json").read_text())
    for case in selected["cases"]:
        suffix = case["case_id"].split("__")[-1]
        design = case["variable_assignments"]
        requested = {"slower_traversal": 6.0, "at_limit_traversal": 6.7056,
                     "faster_traversal": 7.5}[design["speed_mode"]]
        case["target_type"] = "boundary_probe"
        case["paired_probe_id"] = ("rail-speed-15-mph-boundary" if suffix in
                                    ("condition_a", "condition_at", "condition_b") else
                                    "rail-source-axis-" + suffix)
        case["deliberate_differences"] = ["ego_speed", "commanded_approach_speed",
                                           "rail_sight_mode", "rail_exception_state"]
        case["variable_assignments"] = {
            "ego_speed": {"kind": "subject_behavior", "value": None},
            "commanded_approach_speed": {"kind": "controller", "value": requested, "unit": "m/s"},
            "rail_sight_mode": {"kind": "world_setup", "value": design["sight_mode"]},
            "rail_exception_state": {"kind": "world_setup", "value": design["exception_state"]},
        }
        primary = ("ego_speed" if suffix in ("condition_a", "condition_at", "condition_b")
                   else "rail_exception_state" if suffix in
                   ("flagman_duty", "signal_inactive", "signal_active", "signal_not_visible")
                   else "rail_sight_mode")
        case["probe"] = {"primary_variable": primary,
                         "comparison_or_standard": "exact source condition and independent original measurement",
                         "target_value_or_branch": suffix}
        if primary == "ego_speed":
            case["probe"].update(threshold_ref="obligation.numeric_conditions[0]",
                                 operator="<=", unit="mph",
                                 test_value=15.0 if suffix == "condition_at" else
                                 requested / .44704)
            case["epsilon_used"] = {"value": .001, "unit": "mph",
                                    "rationale": "Diagnostic numerical resolution; not a legal tolerance."}
    description = selected["cases"][0]["recording_description"]
    selected["cases"].insert(0, {"case_id": AID + "__baseline", "target_law_id": None,
                                 "target_type": "baseline", "rationale": "Shared neutral rail source anchor",
                                 "variable_assignments": {
                                     "ego_speed": {"kind": "subject_behavior", "value": None},
                                     "commanded_approach_speed": {"kind": "controller", "value": 6.7056, "unit": "m/s"},
                                     "rail_sight_mode": {"kind": "world_setup", "value": "clear_both"},
                                     "rail_exception_state": {"kind": "world_setup", "value": "none"}},
                                 "recording_description": description,
                                 "unresolved_judgment_calls": [j["phrase"] for j in judgments]})
    selected["sweep_specs"] = [{"sweep_id": "lvmc-original-review-" + str(i),
                                "target_law_id": LAW, "judgment_refs": [judgment],
                                "status": "incomplete", "mode": "one_dimensional", "axes": [],
                                "rationale": "Original railway, traffic and exception source review is required before freezing judgment sweep coverage.",
                                "missing_inputs": ["Independent original Native railway and device review"]}
                               for i, judgment in enumerate(judgments)]
    cases_ref = write("canonical-cases.json", selected)
    return write("semantic-index.json", {"format": "worker-semantic-delivery",
                                        "assignment_id": AID,
                                        "stages": {"relevance_batch": rel_batch, "relevance": rel,
                                                   "template": template_ref,
                                                   "judgment_observables": observable_refs,
                                                   "bindings": binding_ref, "cases": cases_ref}})


if __name__ == "__main__":
    print(json.dumps(build()))
