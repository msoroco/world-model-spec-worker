"""Write source-bound canonical draft stages for the selected speed pair."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
LAW = "NRS-484B-267-2a"
TEMPLATE = LAW + "@motor_vehicle_driver"
PHRASES = [
    ("qualifying moving emergency or regulatory vehicle using required flashing lights",
     "Authorization, lamp qualification, movement and original pixels require independent source review."),
    ("speed reasonable and proper under NRS 484B.600(1)",
     "Record original speed and road/weather context without supplying a numeric legal cutoff."),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def build():
    assignment = json.loads((REPO / "inputs" / AID / "assignment.json").read_text())
    law = assignment["law"]
    source = law["text"]
    folder = FOLDER / "proposals"
    folder.mkdir(exist_ok=True)
    relevance = {"cell_id": "C405647", "actor": "motor_vehicle_driver", "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": source,
                                    "applies_to": ["motor_vehicle_driver"],
                                    "relevance_type": "direct", "confidence": "high",
                                    "notes": "The selected driver approaches an already-moving qualifying vehicle."}],
                 "borderline_excluded": []}
    write(folder / "relevance-batch.json", relevance)
    write(folder / "relevance.json", relevance)
    parameters = [
        {"name": "ego_target_speed_mps", "kind": "controller", "range_or_domain": [7, 14]},
        {"name": "emergency_actor_moving", "kind": "world_setup", "range_or_domain": [True, False]},
        {"name": "officer_direction", "kind": "world_setup", "range_or_domain": [True, False]},
    ]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": "motor_vehicle_driver",
                "quote": source, "status": "draft",
                "structure": {"law_id": LAW,
                              "activation": {"condition": "Approaching a qualifying moving or visibly preparing-to-move vehicle using required flashing lights", "numeric_conditions": []},
                              "obligation": {"description": "Decrease speed to a reasonable and proper speed under NRS 484B.600(1)", "type": "must", "numeric_conditions": []},
                              "exceptions": [{"source_clause": "except when otherwise directed by a law enforcement officer",
                                              "description": "Officer direction changes the required response; review original instruction."}],
                              "timing": {"description": "Upon approach; no numeric legal speed or distance cutoff is supplied", "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note in PHRASES]},
                "parameter_refs": parameters}
    write(folder / "template.json", template)
    for index, (phrase, note) in enumerate(PHRASES):
        observable = "qualifying_vehicle_motion_and_lamps" if index == 0 else "ego_speed_response"
        result = {"template_id": TEMPLATE, "phrase": phrase, "note": note, "status": "draft",
                  "observable_requirements": {"observables": [{"name": observable, "unit": "structured", "description": note}],
                                              "context_inputs": [], "sweep_dimensions": [],
                                              "landmarks": [],
                                              "recording_needs": [{"name": "emergency_speed_and_lamps", "unit": "structured",
                                                                   "description": "Original 20 Hz actor speed, lamp and frame join"}],
                                              "limitations": [note, "A synthetic diagnostic cannot establish physical or legal acceptance."]}}
        write(folder / f"judgment_observables_{index}.json", result)
    binding = {"cell_id": "C405647", "actor": "motor_vehicle_driver", "status": "draft",
               "established_contexts": ["Road travel and selected actor roles; original authorization and lamps remain unverified"],
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "context_refs": [],
               "fixed_parameters": [{"name": "selected_road_weather_and_cameras", "value": "held_fixed",
                                     "rationale": "Both cases use the same road, weather, camera and emergency actor construction."}],
               "variable_parameters": [dict(parameter, used_by_laws=[LAW]) for parameter in parameters]}
    write(folder / "bindings.json", binding)
    cases = json.loads((folder / "cases.json").read_text())
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Shared unselected reference; no qualifying approach asserted.",
                "variable_assignments": {"ego_target_speed_mps": {"kind": "controller", "value": 14, "unit": "m/s"},
                                         "emergency_actor_moving": {"kind": "world_setup", "value": False, "unit": "boolean"},
                                         "officer_direction": {"kind": "world_setup", "value": False, "unit": "boolean"}},
                "recording_description": cases["cases"][0]["recording_description"]}
    for case in cases["cases"]:
        case["paired_probe_id"] = AID + "__selected_d6045110__comparison"
        case["deliberate_differences"] = ["ego_target_speed_mps"]
        case["probe"] = {"primary_variable": "ego_target_speed_mps",
                         "comparison_or_standard": "measured original speed response on approach",
                         "target_value_or_branch": case["case_id"][-1]}
        case["unresolved_judgment_calls"] = [phrase for phrase, _ in PHRASES]
    cases["cases"].insert(0, baseline)
    cases["sweep_specs"] = [{"sweep_id": AID + "__raw_speed_response",
                              "target_law_id": LAW, "status": "incomplete",
                              "judgment_refs": [{"phrase": phrase, "note": note} for phrase, note in PHRASES],
                              "rationale": "Two controlled raw speed requests are constructed; original physical and legal source review remains.",
                              "missing_inputs": ["Original Native authorization, lamps, movement and officer review",
                                                 "Reasonable and proper speed judgment under NRS 484B.600(1)"]}]
    write(folder / "cases.json", cases)
    stages = {}
    for name, filename in (("relevance_batch", "relevance-batch.json"), ("relevance", "relevance.json"),
                           ("template", "template.json"), ("bindings", "bindings.json"),
                           ("cases", "cases.json")):
        stages[name] = {"path": "proposals/" + filename, "sha256": sha(folder / filename)}
    stages["judgment_observables"] = [
        {"path": f"proposals/judgment_observables_{index}.json",
         "sha256": sha(folder / f"judgment_observables_{index}.json")}
        for index in range(len(PHRASES))]
    index = {"format": "worker-semantic-delivery", "assignment_id": AID, "stages": stages}
    write(folder / "semantic-index.json", index)
    return {"index_sha256": sha(folder / "semantic-index.json"), "stage_count": 5 + len(PHRASES)}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
