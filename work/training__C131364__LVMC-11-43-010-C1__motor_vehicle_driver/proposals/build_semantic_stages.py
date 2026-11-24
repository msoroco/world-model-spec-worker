"""Author source-bound canonical stage drafts for the left-turn branch."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "proposals"
ASSIGNMENT = json.loads((ROOT.parents[1] / "inputs" / ROOT.name / "assignment.json").read_text())
LAW = ASSIGNMENT["law"]
LAW_ID = ASSIGNMENT["law_id"]
ACTOR = ASSIGNMENT["actor"]
CELL = ASSIGNMENT["cell_id"]
TEMPLATE_ID = f"{LAW_ID}@{ACTOR}"


def save(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def needs(phrase, note, observables):
    return {
        "template_id": TEMPLATE_ID,
        "phrase": phrase,
        "note": note,
        "status": "draft",
        "observable_requirements": {
            "observables": observables,
            "context_inputs": [],
            "sweep_dimensions": [{"name": "requested_circulating_lane", "unit": "lane_id", "description": "Controller lane request; original lane use is separately measured."}],
            "landmarks": [],
            "recording_needs": [{"name": "roundabout_route", "unit": "structured", "description": "Original frame-joined route, map road/lane readback and entry-to-exit history."}],
            "limitations": ["An authored route and synthetic video cannot establish original intent, lane use, physical geometry or a legal verdict."],
        },
    }


relevance = {
    "cell_id": CELL,
    "actor": ACTOR,
    "status": "draft",
    "relevant_laws": [{
        "law_id": LAW_ID,
        "quote": LAW["text"],
        "applies_to": [ACTOR],
        "relevance_type": "specific_match",
        "confidence": "medium",
        "notes": "Fixed multi-lane roundabout and left-turn exit plan; original geometry, intended exit and lane history remain unverified.",
    }],
    "borderline_excluded": [],
}
rel_ref = save("relevance.json", relevance)
batch_ref = save("relevance_batch.json", relevance)

judgments = [
    {"phrase": "intends to exit a roundabout", "note": "Intent itself is not directly observed; the original exit route and context provide limited evidence."},
    {"phrase": "left lane", "note": "Left lane is relative to the original mapped circulatory lane adjacency and travel direction."},
]
template = {
    "template_id": TEMPLATE_ID,
    "law_id": LAW_ID,
    "actor": ACTOR,
    "quote": LAW["text"],
    "status": "draft",
    "structure": {
        "activation": {"condition": "A vehicle operator is within a roundabout and intends to exit by turning left or completing a U-turn.", "numeric_conditions": []},
        "obligation": {"type": "must", "description": "Use the left lane to turn left or complete a U-turn.", "source_clause": "Shall use the left lane to turn left or complete a U-turn.", "numeric_conditions": []},
        "exceptions": [],
        "timing": {"description": "The lane choice must be observed throughout the circulating movement to the actual exit.", "numeric_conditions": []},
        "judgment_calls_needed": judgments,
    },
    "parameter_refs": [
        {"name": "requested_circulating_lane", "kind": "controller", "range_or_domain": "left or right circulating lane request; actual occupancy unverified"},
        {"name": "roundabout_exit_path", "kind": "world_setup", "range_or_domain": "left-turn or U-turn exit route; no legal numeric threshold"},
    ],
}
template_ref = save("template.json", template)

intent = needs(judgments[0]["phrase"], judgments[0]["note"], [
    {"name": "drv.turning", "unit": "structured", "description": "Original entry, circulation and actual exit path with heading."},
    {"name": "kin.heading", "unit": "degrees", "description": "Original heading history for entry-to-exit path review."},
])
lane = needs(judgments[1]["phrase"], judgments[1]["note"], [
    {"name": "st.lane_adjacency", "unit": "structured", "description": "Original map lane ordering and direction."},
    {"name": "rel.occupies", "unit": "structured", "description": "Original per-frame subject lane occupancy and transitions."},
])
judgment_refs = [save("judgment_observables_intent.json", intent), save("judgment_observables_lane.json", lane)]

binding = {
    "cell_id": CELL,
    "actor": ACTOR,
    "status": "draft",
    "established_contexts": [{"name": "frozen_cell", "source": "Frozen C131364 multilane_roundabout / left_turn / lane_allocation assignment"}],
    "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
    "context_refs": [],
    "fixed_parameters": [
        {"name": "roundabout_exit_path", "kind": "world_setup", "value": "same requested left-turn exit route for paired C131364 cases"},
        {"name": "capture_policy", "kind": "world_setup", "value": "20 Hz, 600 frames, four canonical source cameras"},
    ],
    "variable_parameters": [{"name": "requested_circulating_lane", "kind": "controller", "range_or_domain": "left or right circulating lane", "used_by_laws": [LAW_ID]}],
}
binding_ref = save("bindings.json", binding)

construction = json.loads((ROOT / "v2-native-draft/witness_1-construction.json").read_text())
recording = construction["recording_description"]
axis = {
    "variable": "requested_circulating_lane",
    "observable": "requested_circulating_lane",
    "unit": "lane_id",
    "min": -2,
    "max": -1,
    "spacing": 1,
    "range_rationale": "The authored two-lane roundabout has exactly the adjacent lane requests -2 and -1; these are engineering setpoints, not legal thresholds.",
    "spacing_rationale": "One lane-ID step samples both authored circulating lane requests.",
    "feasibility_evidence": "Source-hashed primary constructions and fake-CARLA CPU state-machine test; original lane occupancy remains unverified.",
    "measurement": {"method": "original map lane readback joined to actor frame", "time_window": "all 600 frames, with circulating segment isolated", "statistic": "last"},
}
sweep = {
    "sweep_id": "left_turn_lane_choice",
    "target_law_id": LAW_ID,
    "judgment_refs": deepcopy(judgments),
    "rationale": "Compare two authored circulating lane requests while retaining unresolved intent and left-lane judgments for original-source review.",
    "status": "complete",
    "mode": "one_dimensional",
    "axes": [axis],
    "landmarks": [],
    "variable_assignments": {"requested_circulating_lane": {"kind": "controller", "value": None}},
    "recording_description": recording,
}
def semantic(value):
    if isinstance(value, dict):
        return {k: semantic(v) for k, v in value.items() if k not in {"review_status", "reviewed_at", "approval", "provenance", "dependency_reviews"} and not (k == "status" and v in {"draft", "approved", "reviewed", "unreviewed", "awaiting_review"})}
    if isinstance(value, list):
        return [semantic(item) for item in value]
    return value

def digest(value):
    return hashlib.sha256(json.dumps(semantic(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

sweep["spec_version"] = digest(sweep)
sweep["planned_case_count"] = 2
sweep["selection_order"] = [f"{ROOT.name}__witness_2", f"{ROOT.name}__witness_1"]
baseline = {
    "case_id": f"{ROOT.name}__neutral_baseline",
    "target_law_id": None,
    "target_type": "baseline",
    "rationale": "Unselected context reference; no target outcome or recording selected.",
    "variable_assignments": {"requested_circulating_lane": {"kind": "controller", "value": -1}},
    "recording_description": recording,
    "unresolved_judgment_calls": [],
}
cases = [baseline]
for rank, lane_id in ((0, -2), (1, -1)):
    case_id = sweep["selection_order"][rank]
    cases.append({
        "case_id": case_id,
        "target_law_id": LAW_ID,
        "target_type": "judgment_sweep",
        "rationale": "Requested lane choice; original occupancy, maneuver and source context determine any later interpretation.",
        "paired_probe_id": sweep["sweep_id"],
        "deliberate_differences": ["requested_circulating_lane"],
        "probe": {"primary_variable": "requested_circulating_lane", "comparison_or_standard": "two-lane physical coverage; legal judgment unresolved", "target_value_or_branch": {"requested_circulating_lane": lane_id}},
        "sweep_id": sweep["sweep_id"],
        "sweep_spec_version": sweep["spec_version"],
        "sweep_point": {"requested_circulating_lane": float(lane_id)},
        "selection_rank": rank,
        "variable_assignments": {"requested_circulating_lane": {"kind": "controller", "value": float(lane_id), "note": "Fixed physical sweep setpoint; actual behavior measured separately"}},
        "recording_description": recording,
        "judgment_refs": deepcopy(judgments),
        "sweep_measurements": [{"variable": axis["variable"], "observable": axis["observable"], "unit": axis["unit"], "measurement": axis["measurement"]}],
        "unresolved_judgment_calls": [j["phrase"] for j in judgments],
    })
case_proposal = {"format": "worker-canonical-cases-draft", "cell_id": CELL, "actor": ACTOR, "status": "draft", "sweeps_expanded": True, "sweep_specs": [sweep], "cases": cases}
cases_ref = save("cases.json", case_proposal)

index = {
    "format": "worker-semantic-delivery",
    "assignment_id": ROOT.name,
    "status": "draft",
    "stages": {
        "relevance_batch": batch_ref,
        "relevance": rel_ref,
        "template": template_ref,
        "judgment_observables": judgment_refs,
        "bindings": binding_ref,
        "cases": cases_ref,
    },
}
save("semantic-index.json", index)
print("wrote source-bound semantic stage drafts")


if __name__ == "__main__":
    pass
