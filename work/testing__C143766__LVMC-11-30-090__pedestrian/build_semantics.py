"""Author source-bound draft canonical semantic proposals for LVMC 11.30.090."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROPOSALS = HERE/"proposals"
SOURCE = REPO/"inputs"/HERE.name/"assignment.json"
ASSIGNMENT = json.loads(SOURCE.read_text())
LAW = ASSIGNMENT["law"]["text"]
TEMPLATE = "LVMC-11-30-090@pedestrian"
JUDGMENTS = [
    ("sidewalks are provided", "Sidewalk purpose and actual provision require reviewed site evidence.",
     "sidewalk_roadway_shoulder_trail_context", "source and pixels"),
    ("walk along and upon", "Measure original full-body afoot occupancy and longitudinal progress.",
     "walker_body_xy_m", "m"),
    ("adjacent roadway", "Separate roadway, shoulder, sidewalk and trail boundaries.",
     "sidewalk_roadway_shoulder_trail_context", "source and pixels"),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    path = PROPOSALS/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")
    return {"path": str(path.relative_to(HERE)), "sha256": sha(path)}


def build():
    relevance = {"cell_id": "C143766", "actor": "pedestrian", "status": "draft",
                 "relevant_laws": [{"law_id": "LVMC-11-30-090", "quote": LAW,
                   "applies_to": ["pedestrian"],
                   "relevance_type": "conditional sidewalk use beside an adjacent roadway",
                   "confidence": "low",
                   "notes": "Authored bands and a trail do not establish provided sidewalk purpose or legal application."}],
                 "borderline_excluded": []}
    relevance_ref = write("relevance.json", relevance)
    batch_ref = write("relevance_batch.json", relevance)
    template = {"template_id": TEMPLATE, "law_id": "LVMC-11-30-090",
                "actor": "pedestrian", "quote": LAW, "status": "draft",
                "structure": {"law_id": "LVMC-11-30-090",
                  "activation": {"condition": "A sidewalk is provided beside an adjacent roadway.",
                                 "numeric_conditions": []},
                  "obligation": {"description": "A pedestrian does not walk along and upon that adjacent roadway when the sidewalk is provided.",
                                 "type": "pedestrian_sidewalk_use", "numeric_conditions": []},
                  "exceptions": [],
                  "timing": {"description": "Observe complete original body and walking progress throughout the captured route.",
                             "numeric_conditions": []},
                  "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                             for phrase, note, _, _ in JUDGMENTS]},
                "parameter_refs": [{"name": "pedestrian_route_band",
                                    "kind": "world_setup"}]}
    template_ref = write("template.json", template)
    judgment_refs = []
    for i, (phrase, note, name, unit) in enumerate(JUDGMENTS, 1):
        observation = {"name": name, "unit": unit,
                       "description": note}
        requirement = {"observables": [observation],
                       "context_inputs": [observation] if name.endswith("context") else [],
                       "sweep_dimensions": [], "landmarks": [],
                       "recording_needs": [observation],
                       "limitations": ["Authored geometry and diagnostic pixels do not decide statutory sidewalk purpose, adjacency or legal compliance."]}
        judgment_refs.append(write(f"judgment-{i}.json", {
            "template_id": TEMPLATE, "phrase": phrase, "note": note,
            "status": "draft", "observable_requirements": requirement}))
    binding = {"cell_id": "C143766", "actor": "pedestrian", "status": "draft",
               "established_contexts": ["Authored nonmotorized trail, buffer, sidewalk, shoulder and roadway candidate bands"],
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "context_refs": [],
               "fixed_parameters": [
                   {"name": "corridor_map", "kind": "world_setup",
                    "range_or_domain": "source-hashed candidate OpenDRIVE"},
                   {"name": "sidewalk_and_trail_purpose", "kind": "world_setup",
                    "range_or_domain": "source review pending"}],
               "variable_parameters": [{"name": "pedestrian_route_band",
                     "kind": "world_setup", "range_or_domain": "roadway, sidewalk, shoulder",
                     "used_by_laws": ["LVMC-11-30-090"]}]}
    binding_ref = write("bindings.json", binding)
    cases = []
    for suffix in ("roadway_walk", "sidewalk_walk", "shoulder_walk"):
        config = json.loads((HERE/"cases"/suffix/"config.json").read_text())
        cases.append({"case_id": config["selected_case_id"],
           "target_law_id": "LVMC-11-30-090", "target_type": "boundary_probe",
           "rationale": "Measure whole-body "+suffix+" occupancy against the same authored sidewalk, shoulder and trail context.",
           "variable_assignments": {"pedestrian_route_band": {
               "kind": "world_setup", "value": suffix.removesuffix("_walk")}},
           "paired_probe_id": "roadway_sidewalk_shoulder_contrast",
           "deliberate_differences": ["pedestrian_route_band"],
           "probe": {"primary_variable": "pedestrian_route_band",
                     "comparison_or_standard": "controlled authored band contrast",
                     "target_value_or_branch": suffix},
           "unresolved_judgment_calls": [item[0] for item in JUDGMENTS],
           "recording_description": config["case"]["recording_description"]})
    baseline = dict(cases[0])
    baseline["case_id"] = HERE.name+"__shared_baseline"
    baseline["target_type"] = "baseline"
    baseline["rationale"] = "Shared corridor and afoot route reference for controlled lateral contrasts."
    baseline.pop("paired_probe_id")
    baseline.pop("probe")
    baseline["deliberate_differences"] = []
    sweeps = [{"sweep_id": f"c143766-judgment-{i}",
               "target_law_id": "LVMC-11-30-090", "status": "incomplete",
               "judgment_refs": [{"phrase": phrase, "note": note}],
               "rationale": "No numerical legal boundary follows from the authored corridor.",
               "missing_inputs": ["reviewed site purpose and Native physical/pixel evidence"]}
              for i, (phrase, note, _, _) in enumerate(JUDGMENTS, 1)]
    cases_ref = write("cases.json", {"cell_id": "C143766", "actor": "pedestrian",
                    "status": "draft", "sweeps_expanded": True,
                    "sweep_specs": sweeps, "cases": [baseline, *cases]})
    index = {"format": "worker-semantic-delivery", "assignment_id": HERE.name,
             "source": {"path": str(SOURCE.relative_to(REPO)), "sha256": sha(SOURCE)},
             "stages": {"relevance_batch": batch_ref, "relevance": relevance_ref,
                        "template": template_ref, "judgment_observables": judgment_refs,
                        "bindings": binding_ref, "cases": cases_ref},
             "status": "draft_local_site_and_physical_review_pending"}
    write("semantic-index.json", index)
    return index


if __name__ == "__main__":
    print(json.dumps({"stages": list(build()["stages"])}, indent=2))
