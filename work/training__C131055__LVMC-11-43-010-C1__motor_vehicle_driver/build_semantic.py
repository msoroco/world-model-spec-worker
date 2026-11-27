"""Author source-bound canonical proposals for the selected roundabout exits."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
LAW = "LVMC-11-43-010-C1"
TEMPLATE = LAW + "@motor_vehicle_driver"
QUOTE = ("The following regulations pertain to the operation of vehicles within a "
         "roundabout: The operator of a vehicle who intends to exit a roundabout: "
         "Shall use the left lane to turn left or complete a U-turn.")


def write(name, value):
    path = ROOT / "proposals" / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    relevance = {"cell_id": "C131055", "actor": "motor_vehicle_driver",
        "status": "draft", "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
            "applies_to": ["motor_vehicle_driver"], "relevance_type": "specific_match",
            "confidence": "high", "notes": "Frozen roundabout exit cell; original lane and intent remain unknown."}],
        "borderline_excluded": []}
    rel_batch = write("relevance-batch.json", relevance)
    rel = write("relevance.json", relevance)
    judgments = [
        ("intends to exit a roundabout", "Original requested intent and actual route must be reviewed together.",
         ["entry_exit_intent", "ego_pose", "context_roundabout_topology"]),
        ("left lane to turn left or complete a U-turn", "Lane body occupancy and exit branch require original map and motion.",
         ["roundabout_lane_occupancy", "entry_exit_intent", "context_roundabout_topology"]),
    ]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": "motor_vehicle_driver",
        "status": "draft", "quote": QUOTE, "structure": {
            "activation": {"condition": "The operator intends to exit a roundabout by turning left or completing a U-turn.",
                           "numeric_conditions": []},
            "obligation": {"type": "must", "description": "Use the left lane to turn left or complete a U-turn.",
                           "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Lane use is assessed while circulating toward the intended exit.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note, _ in judgments]},
        "parameter_refs": []}
    template_ref = write("template.json", template)
    judgment_refs = []
    for number, (phrase, note, names) in enumerate(judgments, 1):
        observables = [{"name": name, "unit": "structured" if name != "ego_pose" else "m,deg",
                        "description": note} for name in names]
        requirements = {"observables": observables, "context_inputs": [], "sweep_dimensions": [],
            "landmarks": [], "recording_needs": observables,
            "limitations": ["Original Native map, motion, intent and legal lane meaning require independent review."]}
        judgment_refs.append(write(f"judgment-{number}.json", {"template_id": TEMPLATE,
            "phrase": phrase, "note": note, "status": "draft",
            "observable_requirements": requirements}))
    binding = {"cell_id": "C131055", "actor": "motor_vehicle_driver", "status": "draft",
        "established_contexts": [{"name": "two_lane_roundabout_exit",
            "source": "frozen C131055 catalog cell; original topology and exit route unverified"}],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [
            {"name": "roundabout_lane_choice", "kind": "controller", "range_or_domain": "left or right requested ring lane",
             "used_by_laws": [LAW]},
            {"name": "exit_intent", "kind": "controller", "range_or_domain": "left_turn or u_turn requested exit",
             "used_by_laws": [LAW]}]}
    binding_ref = write("bindings.json", binding)
    cases = json.loads((ROOT / "proposals/cases.json").read_text())
    baseline = {"case_id": ASSIGNMENT + "__baseline", "target_law_id": LAW,
        "target_type": "baseline", "rationale": "Canonical nonselected comparison anchor",
        "probe": {"primary_variable": "roundabout_lane_choice",
                  "comparison_or_standard": "source-observed ring lane and exit route",
                  "target_value_or_branch": "baseline"},
        "variable_assignments": {"roundabout_lane_choice": {"kind": "controller", "value": "left"},
                                 "exit_intent": {"kind": "controller", "value": "left_turn"}},
        "recording_description": cases["cases"][0]["recording_description"],
        "unresolved_judgment_calls": ["original exit intent, map lane and body occupancy"]}
    cases["cases"].insert(0, baseline)
    cases["sweep_specs"] = [{"sweep_id": "c131055_original_lane_intent_review",
        "target_law_id": LAW, "status": "incomplete",
        "judgment_refs": [{"phrase": phrase, "note": note} for phrase, note, _ in judgments],
        "rationale": "Original Native intent, route and ring lane occupancy have not been acquired.",
        "missing_inputs": ["original Native map/control/actor readback", "independent legal review"]}]
    cases_ref = write("canonical-cases.json", cases)
    return write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ASSIGNMENT, "stages": {"relevance_batch": rel_batch,
        "relevance": rel, "template": template_ref, "judgment_observables": judgment_refs,
        "bindings": binding_ref, "cases": cases_ref}})


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
