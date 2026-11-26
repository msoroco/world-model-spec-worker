"""Author exact-law semantic proposals for the four selected door cases."""

import copy
import hashlib
import json
from pathlib import Path

from batch_pipeline.store import digest


folder = Path(__file__).resolve().parents[1]
repo = Path(__file__).resolve().parents[3]
assignment = json.loads((repo / "inputs" / folder.name / "assignment.json").read_text())
law, cell, actor = assignment["law"], assignment["cell"], assignment["actor"]
law_id, cell_id = law["id"], cell["cell_id"]
template_id = law_id + "@" + actor
proposal_path = folder / "proposals/cases.json"
proposal = json.loads(proposal_path.read_text())
selected = proposal["cases"]


def save(name, value):
    path = folder / "proposals" / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {"cell_id": cell_id, "actor": actor, "status": "draft",
             "relevant_laws": [{"law_id": law_id, "quote": law["text"],
                                  "applies_to": [actor], "relevance_type": "specific_match",
                                  "confidence": "high",
                                  "notes": "The selected road loading cell and motor vehicle driver directly match this door rule."}],
             "borderline_excluded": []}
relevance_ref = save("relevance.json", relevance)
batch_ref = save("relevance_batch.json", relevance)

judgments = [
    {"phrase": "closest to passing traffic",
     "note": "Original road direction, passing vehicle trajectory and observed door side must be joined."},
    {"phrase": "immediate loading or unloading of passengers or cargo",
     "note": "Contemporaneous passenger or cargo transfer needs independently reviewed pixels."},
    {"phrase": "longer than is necessary",
     "note": "Observed open interval and activity context are recorded; legal necessity remains unresolved."},
]
template = {"template_id": template_id, "law_id": law_id, "actor": actor,
            "status": "draft", "quote": law["text"],
            "structure": {"activation": {"description": "A vehicle-side door is left open near passing traffic",
                                         "source_clause": "leave open a door on the side of a vehicle which is closest to passing traffic"},
                          "obligation": {"description": "Do not keep the traffic-side door open beyond what immediate loading or unloading requires",
                                         "source_clause": "longer than is necessary for immediate loading or unloading of passengers or cargo"},
                          "exceptions": [],
                          "timing": {"description": "Observed door-open interval relative to contemporaneous transfer activity",
                                     "source_clause": "longer than is necessary"},
                          "judgment_calls_needed": judgments},
            "parameter_refs": [
                {"name": "transfer_kind", "kind": "world_setup",
                 "range_or_domain": "passenger or cargo source context"},
                {"name": "requested_close_frame", "kind": "controller",
                 "range_or_domain": "212 or 400 frame request; observed duration measured separately"}]}
template_ref = save("template.json", template)

need_map = [
    ["st.lane", "sig.door_open"],
    ["ru.occupant_count", "ru.pedestrian"],
    ["sig.door_open", "kin.time"],
]
observable_refs = []
for index, (judgment, names) in enumerate(zip(judgments, need_map)):
    needs = [{"name": name, "unit": "structured",
              "description": "Original source frame join and independently reviewed four-camera pixels"}
             for name in names]
    result = {"template_id": template_id, "phrase": judgment["phrase"],
              "note": judgment["note"], "status": "draft",
              "observable_requirements": {
                  "observables": copy.deepcopy(needs), "context_inputs": [],
                  "sweep_dimensions": [{"name": "requested_close_frame", "unit": "frame",
                                        "description": "Requested actuation frame; actual door interval is measured independently"}],
                  "landmarks": [], "recording_needs": copy.deepcopy(needs),
                  "limitations": ["Actuator command is not observed door pose.",
                                  "No numeric legal necessity threshold is inferred."]}}
    observable_refs.append(save(f"judgment_observables_{index}.json", result))

variables = [
    {"name": "transfer_kind", "kind": "world_setup", "range_or_domain": "passenger or cargo",
     "used_by_laws": [law_id]},
    {"name": "requested_close_frame", "kind": "controller", "range_or_domain": "212 or 400 frame request",
     "used_by_laws": [law_id]},
]
binding = {"cell_id": cell_id, "actor": actor, "status": "draft",
           "established_contexts": [{"name": "roadside_loading_context",
                                     "source": "Frozen cell; original map and physical source review pending"}],
           "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
           "context_refs": [], "fixed_parameters": [], "variable_parameters": variables}
binding_ref = save("bindings.json", binding)

for index, case in enumerate(selected):
    case["target_type"] = "judgment_sweep"
    case["variable_assignments"]["transfer_kind"]["kind"] = "world_setup"
    case["paired_probe_id"] = folder.name + ("__passenger_comparison" if index < 2 else "__cargo_comparison")
    case["deliberate_differences"] = ["requested_close_frame"]
    case["probe"] = {"primary_variable": "requested_close_frame",
                     "comparison_or_standard": "controlled requested actuation timing; legal necessity unresolved",
                     "target_value_or_branch": case["variable_assignments"]["requested_close_frame"]["value"]}
    case["unresolved_judgment_calls"] = [j["phrase"] for j in judgments]

baseline = copy.deepcopy(selected[0])
baseline["case_id"] = folder.name + "__neutral_baseline"
baseline["target_type"] = "baseline"
baseline["rationale"] = "Shared neutral context reference for the two controlled request-time pairs; not a selected recording"
baseline.pop("paired_probe_id", None)
baseline.pop("deliberate_differences", None)
baseline.pop("probe", None)

sweeps = []
for label, cases in (("passenger", selected[:2]), ("cargo", selected[2:])):
    spec = {"sweep_id": folder.name + "__" + label + "_door_schedule",
            "target_law_id": law_id,
            "judgment_refs": copy.deepcopy(judgments),
            "rationale": "Two fixed door-close requests for physical coverage; compare observed pixels and transfer context without a legal duration threshold.",
            "status": "complete", "mode": "one_dimensional",
            "axes": [{"variable": "requested_close_frame", "observable": "requested_close_frame",
                      "unit": "frame", "min": 212, "max": 400, "spacing": 188,
                      "range_rationale": "Two authored close commands matched to the selected pair.",
                      "spacing_rationale": "188 frames separate the selected requests at 20 Hz.",
                      "feasibility_evidence": "Four exact CPU offline and synthetic saved-source checks pass.",
                      "measurement": {"method": "Read requested actuation frame separately from reviewed actual door interval",
                                      "time_window": "600 original Native frames", "statistic": "first"}}],
            "landmarks": [],
            "variable_assignments": copy.deepcopy(cases[0]["variable_assignments"]),
            "recording_description": copy.deepcopy(cases[0]["recording_description"])}
    version = digest(spec)
    spec["spec_version"] = version
    spec["planned_case_count"] = 2
    spec["selection_order"] = [case["case_id"] for case in cases]
    for rank, case in enumerate(cases):
        case["sweep_id"] = spec["sweep_id"]
        case["sweep_spec_version"] = version
        case["sweep_point"] = {"requested_close_frame": float(case["variable_assignments"]["requested_close_frame"]["value"])}
        case["selection_rank"] = rank
    sweeps.append(spec)
proposal["cases"] = selected + [baseline]
proposal["sweep_specs"] = sweeps
cases_ref = save("cases.json", proposal)
index = {"format": "worker-semantic-delivery", "assignment_id": folder.name,
         "stages": {"relevance_batch": batch_ref, "relevance": relevance_ref,
                    "template": template_ref, "judgment_observables": observable_refs,
                    "bindings": binding_ref, "cases": cases_ref}}
save("semantic-index.json", index)
print("authored exact-law semantic chain and two source-bounded schedule sweeps")
