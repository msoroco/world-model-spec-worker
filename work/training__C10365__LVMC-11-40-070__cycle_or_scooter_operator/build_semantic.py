"""Build canonical draft stages for the selected device and officer pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / "proposals"
AID = HERE.name
LAW = "LVMC-11-40-070"
ACTOR = "cycle_or_scooter_operator"
TEMPLATE = LAW + "@" + ACTOR


def save(name, data):
    path = PROPOSALS / name
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def variable(kind, value, source):
    return {"kind": kind, "value": value, "unit": "structured", "source": source}


def build():
    original = json.loads((HERE / "../../inputs" / AID / "assignment.json").resolve().read_text())
    quote = original["law"]["text"]
    recording = json.loads((PROPOSALS / "cases.json").read_text())["cases"][0]["recording_description"]
    relevance = {"cell_id": "C10365", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
                                    "relevance_type": "direct", "confidence": "high",
                                    "notes": "The frozen rider cell names a Police Officer; authority and device applicability need original review."}],
                 "borderline_excluded": []}
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": quote,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "A person operates a bicycle, electric bicycle, or electric scooter at an applicable official traffic-control device.", "numeric_conditions": []},
                              "obligation": {"type": "must", "description": "Obey official traffic-control signals, signs, and devices applicable to vehicles.", "numeric_conditions": []},
                              "exceptions": [{"trigger": "A Police Officer directs otherwise.",
                                              "effect": "The operator follows the Police Officer's contrary direction.",
                                              "replacement_obligation": "Follow the Police Officer's direction.",
                                              "source_clause": "unless otherwise directed by a Police Officer"}],
                              "timing": {"description": "Observe applicable control and any officer direction before crossing the device station.", "numeric_conditions": []},
                              "judgment_calls_needed": []},
                "parameter_refs": [{"name": "officer_cue_requested", "kind": "controller",
                                    "range_or_domain": "no contrary direction or contrary direction"},
                                   {"name": "observed_officer_direction", "kind": "subject_behavior",
                                    "range_or_domain": "original visible instruction and response, unresolved"}]}
    bindings = {"cell_id": "C10365", "actor": ACTOR, "status": "draft",
                "established_contexts": ["Alley travel and Police Officer are frozen planning context; original control and authority remain unverified."],
                "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
                "context_refs": [], "fixed_parameters": [],
                "variable_parameters": [
                    {"name": "officer_cue_requested", "kind": "controller",
                     "range_or_domain": "no contrary direction or contrary direction", "used_by_laws": [LAW]},
                    {"name": "observed_officer_direction", "kind": "subject_behavior",
                     "range_or_domain": "original visible instruction and rider response", "used_by_laws": [LAW]}]}
    pair = AID + "__comparison"
    cases = []
    for suffix, cue, target in (("a", "no_contrary_direction", "compliant_attempt"),
                                ("b", "contrary_direction", "violating_attempt")):
        values = {"officer_cue_requested": variable("controller", cue, "planned cue; original authority and visibility pending"),
                  "observed_officer_direction": variable("subject_behavior", None, "original Native capture and independent review")}
        cases.append({"case_id": AID + "__probe_" + suffix, "target_law_id": LAW,
                      "target_type": target,
                      "rationale": "Device-response attempt; the officer exception and legal outcome remain unresolved until original review.",
                      "variable_assignments": values, "unresolved_judgment_calls": [],
                      "recording_description": recording, "paired_probe_id": pair,
                      "deliberate_differences": ["officer_cue_requested"],
                      "probe": {"primary_variable": "officer_cue_requested",
                                "comparison_or_standard": "same applicable device with requested officer direction changed",
                                "target_value_or_branch": cue}})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Shared source and device review contract without an outcome claim.",
                "variable_assignments": {"officer_cue_requested": variable("controller", None, "undetermined baseline cue"),
                                         "observed_officer_direction": variable("subject_behavior", None, "original Native review")},
                "unresolved_judgment_calls": [], "recording_description": recording}
    proposed = {"cell_id": "C10365", "actor": ACTOR, "status": "draft",
                "cases": [baseline] + cases, "sweep_specs": [], "sweeps_expanded": True}
    references = {"relevance_batch": save("relevance-batch.json", relevance),
                  "relevance": save("relevance.json", relevance),
                  "template": save("template.json", template),
                  "judgment_observables": [], "bindings": save("bindings.json", bindings),
                  "cases": save("cases.json", proposed)}
    save("semantic-index.json", {"format": "worker-semantic-delivery",
                                 "assignment_id": AID, "stages": references})


if __name__ == "__main__":
    build()
