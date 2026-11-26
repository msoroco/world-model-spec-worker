"""Author canonical draft stages for exact NRS angle-device comparisons."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = HERE.parents[2]
PROPOSALS = FOLDER / "proposals"
ASSIGNMENT = FOLDER.name
LAW = "NRS-484B-460"
ACTOR = "motor_vehicle_driver"
TEXT = ("Upon those highways which have official traffic-control devices permitting "
        "angle parking, a person shall not stop, stand or park a vehicle other than "
        "at the angle to the curb or edge of the highway indicated by such devices.")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": "proposals/" + name, "sha256": sha(path)}


def parameter(name, kind, domain):
    return {"name": name, "kind": kind, "range_or_domain": domain}


def value(kind, item, unit):
    return {"kind": kind, "value": item, "unit": unit}


def build():
    relevance = {"cell_id": "C385967", "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": TEXT, "applies_to": [ACTOR],
            "relevance_type": "specific_match", "confidence": "high",
            "notes": "Exact one-way angle-parking designation cell; original official device and governed curb require source review."}],
        "borderline_excluded": []}
    ref_batch = write("relevance_batch.json", relevance)
    ref_relevance = write("relevance.json", relevance)
    refs = [parameter("requested_at_rest_heading_deg", "controller",
                      "angle requested at the authored curb, degrees"),
            parameter("observed_angle_to_curb_deg", "subject_behavior",
                      "original Native heading relative to curb, degrees"),
            parameter("indicated_angle_to_curb_deg", "world_setup",
                      "source-read official device angle, degrees"),
            parameter("parking_activity", "world_setup",
                      "stopped, standing or parked activity context")]
    template = {"template_id": LAW + "@" + ACTOR, "law_id": LAW,
        "actor": ACTOR, "status": "draft", "quote": TEXT,
        "structure": {"law_id": LAW,
            "activation": {"condition": "Official device permits angle parking on the governed highway and vehicle is stopped, standing or parked", "numeric_conditions": []},
            "obligation": {"type": "must_not",
                "description": "Stop, stand or park at an angle other than the device-indicated angle to the curb or highway edge",
                "source_clause": "shall not stop, stand or park a vehicle other than at the angle to the curb or edge of the highway indicated by such devices",
                "numeric_conditions": []},
            "exceptions": [], "timing": {"description": "During the stopped, standing or parked interval; no numeric tolerance appears in source law", "numeric_conditions": []},
            "judgment_calls_needed": []}, "parameter_refs": refs}
    ref_template = write("template.json", template)
    bindings = {"cell_id": "C385967", "actor": ACTOR, "status": "draft",
        "established_contexts": [{"name": "one_way_angle_parking_candidate",
            "source": "frozen catalog cell; official source and authority remain for original review"}],
        "law_refs": [{"template_id": LAW + "@" + ACTOR, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{**item, "used_by_laws": [LAW]} for item in refs]}
    ref_bindings = write("bindings.json", bindings)
    proposal_cases = []
    for action, activity in (("park", "parked"), ("stop", "stopped"),
                             ("stand", "standing")):
      for letter, heading, kind in (("a", 45, "compliant_attempt"),
                                    ("b", 70, "violating_attempt")):
        suffix = "" if action == "park" else action + "_"
        case = ASSIGNMENT + "__selected_03f318de__" + suffix + "condition_" + letter
        construction = json.loads((HERE / f"selected-{action+'-' if action != 'park' else ''}{letter}-construction.json").read_text())
        proposal_cases.append({"case_id": case, "target_law_id": LAW,
            "target_type": kind,
            "rationale": "Source-bound " + action + " angle contrast at one governed curb; actual device, activity and pixels remain for independent review",
            "paired_probe_id": ASSIGNMENT + "__selected_03f318de__" + suffix + "comparison",
            "deliberate_differences": ["requested_at_rest_heading_deg"],
            "probe": {"primary_variable": "requested_at_rest_heading_deg",
                      "comparison_or_standard": "device-indicated angle to curb",
                      "target_value_or_branch": heading},
            "variable_assignments": {
                "requested_at_rest_heading_deg": value("controller", heading, "deg"),
                "observed_angle_to_curb_deg": value("subject_behavior", None, "deg"),
                "indicated_angle_to_curb_deg": value("world_setup", 45, "deg"),
                "parking_activity": value("world_setup", activity, "categorical")},
            "unresolved_judgment_calls": ["Official device, governed curb and original physical activity require review"],
            "recording_description": construction["recording_description"]})
    baseline = dict(proposal_cases[0])
    baseline.update({"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
                     "target_type": "baseline", "rationale": "Shared governed curb and device context; no verdict"})
    baseline.pop("paired_probe_id")
    baseline.pop("deliberate_differences")
    baseline.pop("probe")
    ref_cases = write("cases.json", {"cell_id": "C385967", "actor": ACTOR,
        "status": "draft", "sweep_specs": [], "cases": [baseline, *proposal_cases]})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ASSIGNMENT,
        "stages": {"relevance_batch": ref_batch, "relevance": ref_relevance,
                   "template": ref_template, "judgment_observables": [],
                   "bindings": ref_bindings, "cases": ref_cases}})
    print(json.dumps({"cases": [c["case_id"] for c in proposal_cases],
                      "semantic_index_sha256": sha(PROPOSALS / "semantic-index.json")}, sort_keys=True))


if __name__ == "__main__":
    build()
