"""Author exact-law semantic stages for the residential driveway branch."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = json.loads((REPO / "inputs/testing__C213645__LVMC-11-20-060__motor_vehicle_driver/assignment.json").read_text())
PLAN = json.loads((HERE / "case-plan.json").read_text())
PROPOSALS = HERE / "proposals"
LAW = ASSIGNMENT["law_id"]
ACTOR = ASSIGNMENT["actor"]
TEMPLATE_ID = LAW + "@" + ACTOR
QUOTE = ASSIGNMENT["law"]["text"]


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": "proposals/" + name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {"cell_id": ASSIGNMENT["cell_id"], "actor": ACTOR, "status": "draft",
             "relevant_laws": [{"law_id": LAW, "quote": QUOTE, "applies_to": [ACTOR],
                                 "relevance_type": "assigned driveway entry duty",
                                 "confidence": "high",
                                 "notes": "The selected residence-district private-driveway branch requires original context review."}],
             "borderline_excluded": []}
relevance_batch_ref = write("relevance_batch.json", relevance)
relevance_ref = write("relevance.json", relevance)

judgments = [
    {"phrase": "immediately prior", "note": "The law gives no distance or time cutoff for the stop location."},
    {"phrase": "as may be necessary to avoid collision", "note": "Pedestrian necessity requires the original motion and conflict context."},
    {"phrase": "right-of-way to all vehicles approaching", "note": "Approach and precedence require original roadway motion and context."},
]
parameters = [
    {"name": "ego_entry_behavior", "kind": "controller",
     "range_or_domain": "requested stop before sidewalk or requested rolling entry"},
    {"name": "pedestrian_mode", "kind": "world_setup",
     "range_or_domain": "absent or crossing with authored yield/intrude response"},
    {"name": "roadway_vehicle_mode", "kind": "world_setup",
     "range_or_domain": "clear or left/right approaching with authored yield/intrude response"},
]
template = {"template_id": TEMPLATE_ID, "law_id": LAW, "actor": ACTOR, "quote": QUOTE,
            "structure": {"law_id": LAW,
                          "activation": {"condition": "Driver of vehicle in a business or residence district emerges from alley, driveway or building toward sidewalk and roadway.", "numeric_conditions": []},
                          "obligation": {"description": "Stop immediately prior to sidewalk or sidewalk area, yield to pedestrians as necessary to avoid collision, and yield to all approaching roadway vehicles upon entry.",
                                         "type": "must", "numeric_conditions": []},
                          "exceptions": [],
                          "timing": {"description": "Before sidewalk entry and upon roadway entry.", "numeric_conditions": []},
                          "judgment_calls_needed": judgments}, "parameter_refs": parameters}
template_ref = write("template.json", template)

observable_refs = []
observed_channels = ("driveway_sidewalk_roadway_geometry", "ego_motion_and_body",
                     "pedestrian_motion_and_body", "approaching_vehicle_motion_and_body",
                     "frame_map_and_cameras")
for index, judgment in enumerate(judgments):
    requirements = {"observables": [{"name": name, "unit": "structured",
                                      "description": "original frame-joined " + name.replace("_", " ")}
                                     for name in observed_channels],
                    "context_inputs": [{"name": "reviewed_residential_driveway_context",
                                        "unit": "source_packet",
                                        "description": "reviewed original residence frontage, access, sidewalk and connected road"}],
                    "sweep_dimensions": [], "landmarks": [],
                    "recording_needs": [{"name": name, "unit": "structured",
                                         "description": "retain original per-frame " + name.replace("_", " ")}
                                        for name in observed_channels],
                    "limitations": ["Original source measurements leave the statutory judgment unresolved.",
                                    "A synthetic diagnostic verifies software only."]}
    value = {"template_id": TEMPLATE_ID, "phrase": judgment["phrase"],
             "note": judgment["note"], "status": "draft", "observable_requirements": requirements}
    observable_refs.append(write("judgment-observables-" + str(index + 1) + ".json", value))

bindings = {"cell_id": ASSIGNMENT["cell_id"], "actor": ACTOR, "status": "draft",
            "established_contexts": ["Assigned residential private driveway, intervening sidewalk and connected roadway are construction targets requiring original survey."],
            "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
            "context_refs": [], "fixed_parameters": [],
            "variable_parameters": [dict(parameter, used_by_laws=[LAW]) for parameter in parameters]}
binding_ref = write("bindings.json", bindings)

recording = json.loads((HERE / "construction.json").read_text())["recording_description"]


def assignments(case):
    return {
        "ego_entry_behavior": {"kind": "controller", "value": case["controller"]["entry_behavior"]},
        "pedestrian_mode": {"kind": "world_setup", "value": case["world_setup"]["pedestrian"]},
        "roadway_vehicle_mode": {"kind": "world_setup", "value": case["world_setup"]["roadway_vehicle"]},
    }


baseline = {"case_id": PLAN["assignment_id"] + "__baseline", "target_law_id": None,
            "target_type": "baseline", "rationale": "Fixed clear residential driveway reference; no legal outcome label.",
            "variable_assignments": assignments(PLAN["cases"][0]),
            "unresolved_judgment_calls": [j["phrase"] for j in judgments],
            "recording_description": recording}
pair_names = {"sidewalk": "ego_entry_behavior", "pedestrian": "pedestrian_mode",
              "roadway_left": "roadway_vehicle_mode", "roadway_right": "roadway_vehicle_mode"}
cases = [baseline]
for row in PLAN["cases"]:
    name = row["case_id"].split("__")[-1]
    pair = name.rsplit("_", 1)[0]
    if pair not in pair_names:
        pair = "sidewalk"
    primary = pair_names[pair]
    cases.append({"case_id": row["case_id"], "target_law_id": LAW,
                  "target_type": "boundary_probe", "rationale": row["deliberate_condition"],
                  "variable_assignments": assignments(row),
                  "unresolved_judgment_calls": [j["phrase"] for j in judgments],
                  "paired_probe_id": pair, "deliberate_differences": [primary],
                  "probe": {"primary_variable": primary,
                            "comparison_or_standard": "fixed-condition source measurement without legal cutoff",
                            "target_value_or_branch": name},
                  "recording_description": recording})

sweeps = [{"sweep_id": "unresolved-" + str(index + 1), "target_law_id": LAW,
           "judgment_refs": [judgment], "status": "incomplete",
           "rationale": "Source has no authoritative numeric legal cutoff or reviewed physical sweep range.",
           "missing_inputs": ["reviewed original physical feasibility range and source-backed spacing for " + judgment["phrase"]]}
          for index, judgment in enumerate(judgments)]
cases_ref = write("cases.json", {"cell_id": ASSIGNMENT["cell_id"], "actor": ACTOR,
                                  "status": "draft", "cases": cases, "sweep_specs": sweeps,
                                  "sweeps_expanded": True})
index = {"format": "worker-semantic-delivery", "assignment_id": PLAN["assignment_id"],
         "stages": {"relevance_batch": relevance_batch_ref, "relevance": relevance_ref,
                    "template": template_ref, "judgment_observables": observable_refs,
                    "bindings": binding_ref, "cases": cases_ref}}
write("semantic-index.json", index)
