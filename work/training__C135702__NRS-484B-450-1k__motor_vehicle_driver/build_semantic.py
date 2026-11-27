"""Construct source-scoped semantic drafts without resolving the traffic judgment."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
LAW = "NRS-484B-450-1k"
CELL = "C135702"
ACTOR = "motor_vehicle_driver"
PHRASE = "when stopping, standing or parking would obstruct traffic"
NOTE = "Original same-time traffic movement and obstruction effects require independent review."


def write(name, value):
    path = ROOT / "proposals" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    assignment = json.loads((REPO / "inputs" / AID / "assignment.json").read_text())
    quote = assignment["law"]["text"]
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote,
                                    "applies_to": [ACTOR], "relevance_type": "specific_match",
                                    "confidence": "high",
                                    "notes": "The frozen park maneuver targets the exact highway obstruction clause."}],
                 "borderline_excluded": []}
    refs = {}
    refs["relevance_batch"] = write("relevance_batch.json", relevance)
    refs["relevance"] = write("relevance.json", relevance)
    template = {"template_id": LAW + "@" + ACTOR, "law_id": LAW,
                "actor": ACTOR, "status": "draft", "quote": quote,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "Vehicle stops, stands or parks alongside or opposite a source-reviewed highway excavation or obstruction.", "numeric_conditions": []},
                              "obligation": {"type": "must_not", "description": "Do not stop, stand or park there when the activity would obstruct traffic unless an exact exception applies.", "numeric_conditions": []},
                              "exceptions": [
                                  {"source_clause": "except when necessary to avoid conflict with other traffic", "description": "Retain original traffic necessity evidence."},
                                  {"source_clause": "in compliance with law", "description": "Retain the applicable original legal authority."},
                                  {"source_clause": "the directions of a police officer", "description": "Retain original officer direction and timing."},
                                  {"source_clause": "official traffic-control device", "description": "Retain original official device identity and indication."}],
                              "timing": {"description": "Observe the whole stopping, standing or parking interval with same-time traffic response.", "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": PHRASE, "note": NOTE}]},
                "parameter_refs": [
                    {"name": "obstruction_kind", "kind": "world_setup", "range_or_domain": "source-reviewed excavation or physical obstruction"},
                    {"name": "park_y_m", "kind": "controller", "range_or_domain": "authored parked vehicle transverse position in m"},
                    {"name": "observed_open_width_m", "kind": "subject_behavior", "range_or_domain": "same-frame measured free transverse opening or unknown"},
                    {"name": "observed_passing_response", "kind": "subject_behavior", "range_or_domain": "original traffic response or unknown"}]}
    refs["template"] = write("template.json", template)
    judgment = {"template_id": template["template_id"], "phrase": PHRASE,
                "note": NOTE, "status": "draft", "observable_requirements": {
                    "observables": [{"name": "observed_passing_response", "unit": "structured", "description": "Original traffic motion and response, without a legal label"}],
                    "context_inputs": [{"name": "exception_authority", "unit": "structured", "description": "Original records for all four statutory exceptions"}],
                    "sweep_dimensions": [{"name": "observed_open_width_m", "unit": "m", "description": "Measured free opening after the parked body realizes"}],
                    "landmarks": [],
                    "recording_needs": [{"name": "kin.velocity", "unit": "structured", "description": "Same-frame passing and parked body velocity"},
                                        {"name": "st.lane_width", "unit": "structured", "description": "Original road and sampled opening geometry"},
                                        {"name": "drv.hard_deceleration", "unit": "structured", "description": "Measured passing response without a legal cutoff"}],
                    "limitations": ["A finite authored opening and synthetic response do not decide whether traffic would be obstructed."]}}
    refs["judgment_observables"] = [write("judgment-0.json", judgment)]
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "established_contexts": [],
               "law_refs": [{"template_id": template["template_id"], "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [dict(parameter, used_by_laws=[LAW])
                                       for parameter in template["parameter_refs"]]}
    refs["bindings"] = write("bindings.json", binding)
    cases = json.loads((ROOT / "proposals" / "cases.json").read_text())
    cases["sweep_specs"] = [{"sweep_id": "traffic-obstruction-physical-coverage",
                             "target_law_id": LAW,
                             "judgment_refs": [{"phrase": PHRASE, "note": NOTE}],
                             "status": "incomplete",
                             "rationale": "The existing two parked positions sample opening geometry, but do not establish physically feasible response coverage for an exact traffic-obstruction sweep.",
                             "missing_inputs": ["Original Native passing response across a calibrated, fixed geometry range and reviewed source exception authority."]}]
    refs["cases"] = write("cases.json", cases)
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": AID, "stages": refs})


if __name__ == "__main__":
    build()
