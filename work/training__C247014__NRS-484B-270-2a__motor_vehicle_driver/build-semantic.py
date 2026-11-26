"""Build source-bound draft semantic stages for the selected bicycle-pass cases."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = "NRS-484B-270-2a"
ACTOR = "motor_vehicle_driver"
CELL = "C247014"
TEMPLATE = LAW + "@" + ACTOR
OUT = HERE / "proposals"


def save(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def variable(kind, value, source):
    return {"kind": kind, "value": value, "unit": "structured", "source": source}


def observable(name, unit, description):
    return {"name": name, "unit": unit, "description": description}


def main():
    original = json.loads((HERE.parent.parent / "inputs" / AID / "assignment.json").read_text())
    quote = original["law"]["text"]
    manifest = json.loads((HERE / "selected-native-draft-manifest.json").read_text())
    recording = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())["recording_description"]
    relevance = {
        "cell_id": CELL, "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
                           "relevance_type": "direct", "confidence": "high",
                           "notes": "Exact frozen same-direction multilane bicycle-pass cell."}],
        "borderline_excluded": [],
    }
    template = {
        "template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "status": "draft",
        "quote": quote,
        "structure": {
            "law_id": LAW,
            "activation": {"condition": "Driver overtakes or passes a covered rider going the same direction on a roadway with more than one same-direction lane.", "numeric_conditions": []},
            "obligation": {"type": "must", "description": "Exercise due care and, when the immediate-left lane is available and movement reasonably safe, move into that lane for the pass.", "numeric_conditions": []},
            "exceptions": [{"source_clause": "if the lane is available and moving into the lane is reasonably safe",
                            "description": "The left-lane movement duty is conditional on both source conditions."}],
            "timing": {"description": "Move into the immediate-left lane before the overtaking pass and retain it through the passing interval.", "numeric_conditions": []},
            "judgment_calls_needed": [
                {"phrase": "due care", "note": "No legal threshold inferred from a motion trace."},
                {"phrase": "reasonably safe", "note": "Original traffic context and independent review required."},
            ],
        },
        "parameter_refs": [
            {"name": "requested_lane_move", "kind": "controller", "range_or_domain": "move to immediate left before pass or remain in right lane"},
            {"name": "left_lane_occupant_plan", "kind": "world_setup", "range_or_domain": "occupied or empty in authored scene"},
            {"name": "closing_left_vehicle_context", "kind": "world_setup", "range_or_domain": "closing vehicle present or absent in authored scene"},
            {"name": "measured_lane_position", "kind": "subject_behavior", "range_or_domain": "original per-frame lane readback"},
            {"name": "measured_pass", "kind": "subject_behavior", "range_or_domain": "original per-frame body-overlap pass"},
        ],
    }
    judgments = []
    for phrase, note, measured, context in (
        ("due care", "No legal threshold inferred from a motion trace.",
         [observable("ego_pose", "structured", "Original subject motion and lane history"),
          observable("cyclist_pose", "structured", "Original rider motion and position")],
         [observable("left_lane_availability", "source context", "Original lane and traffic context")]),
        ("reasonably safe", "Original traffic context and independent review required.",
         [observable("left_lane_occupancy", "structured", "Original adjacent-lane occupancy history")],
         [observable("left_lane_availability", "source context", "Original availability and traffic context")]),
    ):
        judgments.append({
            "template_id": TEMPLATE, "phrase": phrase, "note": note, "status": "draft",
            "observable_requirements": {
                "observables": measured, "context_inputs": context,
                "sweep_dimensions": [], "landmarks": [],
                "recording_needs": measured,
                "limitations": ["Retain source measurements for independent judgment; this draft supplies no legal decision bound."],
            },
        })
    bindings = {
        "cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": ["Frozen cell specifies the planned scene; original lane and actor state require readback."],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}], "context_refs": [],
        "fixed_parameters": [],
        "variable_parameters": [
            {"name": name, "kind": kind, "range_or_domain": domain, "used_by_laws": [LAW]}
            for name, kind, domain in (
                ("requested_lane_move", "controller", "left-before-pass or hold-right request"),
                ("left_lane_occupant_plan", "world_setup", "authored occupant present or absent"),
                ("closing_left_vehicle_context", "world_setup", "authored closing left-lane actor present or absent"),
                ("measured_lane_position", "subject_behavior", "original per-frame lane readback"),
                ("measured_pass", "subject_behavior", "original measured passing interval"),
            )
        ],
    }
    shared = {
        "requested_lane_move": variable("controller", "hold_right", "Native controller plan; observed motion separate"),
        "left_lane_occupant_plan": variable("world_setup", "absent", "Native scene plan; observed occupancy separate"),
        "closing_left_vehicle_context": variable("world_setup", "absent", "Native scene plan; observed closing motion separate"),
        "measured_lane_position": variable("subject_behavior", None, "Original Native lane readback"),
        "measured_pass": variable("subject_behavior", None, "Original Native participant poses"),
    }
    baseline = {
        "case_id": AID + "__baseline", "target_law_id": None, "target_type": "baseline",
        "rationale": "Shared roadway, rider, camera and measurement context without a selected outcome.",
        "variable_assignments": shared, "unresolved_judgment_calls": [],
        "recording_description": recording,
    }
    cases = [baseline]
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(AID + "__")
        values = json.loads(json.dumps(shared))
        values["requested_lane_move"]["value"] = "left_before_pass" if suffix == "witness_1" else "hold_right"
        values["left_lane_occupant_plan"]["value"] = "present" if suffix == "exception_1_2" else "absent"
        values["closing_left_vehicle_context"]["value"] = "approaching" if suffix == "exception_unsafe_available" else "absent"
        primary = ("closing_left_vehicle_context" if suffix == "exception_unsafe_available" else
                   ("left_lane_occupant_plan" if suffix.startswith("exception") else "requested_lane_move"))
        group = ("unsafe_available" if suffix == "exception_unsafe_available" else
                 ("exception_1" if suffix.startswith("exception") else "witness"))
        cases.append({
            "case_id": entry["case_id"], "target_law_id": LAW,
            "target_type": "boundary_probe",
            "rationale": "Source-bound physical comparison target; legal judgment and original realization remain unaccepted.",
            "variable_assignments": values,
            "unresolved_judgment_calls": ["due care", "reasonably safe"],
            "recording_description": recording,
            "paired_probe_id": AID + "__" + group + "_comparison",
            "deliberate_differences": [primary],
            "probe": {"primary_variable": primary,
                      "comparison_or_standard": "Paired authored physical variation; no legal bound",
                      "target_value_or_branch": values[primary]["value"]},
        })
    sweep_refs = [{"phrase": j["phrase"], "note": j["note"]} for j in judgments]
    proposed = {
        "cell_id": CELL, "actor": ACTOR, "status": "draft", "cases": cases,
        "sweep_specs": [{"sweep_id": AID + "__judgment_coverage", "target_law_id": LAW,
                         "judgment_refs": sweep_refs,
                         "rationale": "Physical coverage plan requires source-grounded ranges and feasible original motion.",
                         "status": "incomplete",
                         "missing_inputs": ["Original Native lane-change feasibility", "Source-grounded physical ranges for due-care and reasonable-safety observables"]}],
        "sweeps_expanded": True,
    }
    refs = {
        "relevance_batch": save("relevance-batch.json", relevance),
        "relevance": save("relevance.json", relevance),
        "template": save("template.json", template),
        "judgment_observables": [save("judgment-" + str(i + 1) + ".json", j) for i, j in enumerate(judgments)],
        "bindings": save("bindings.json", bindings),
        "cases": save("cases.json", proposed),
    }
    save("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": AID, "stages": refs})


if __name__ == "__main__":
    main()
