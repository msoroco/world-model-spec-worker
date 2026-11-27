"""Author the exact draft semantic stage chain for the three parking probes."""

import hashlib
import json
from pathlib import Path

from duration_policy import TARGETS, APPROACH_DISTANCE_M, RATE_HZ, stop_frame


HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(name, value):
    path = HERE / "proposals" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return {"path": str(path.relative_to(HERE)), "sha256": digest(path)}


def build():
    original = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    law = original["law"]
    relevance = {"cell_id": original["cell_id"], "actor": original["actor"],
                 "status": "draft", "relevant_laws": [{"law_id": law["id"],
                 "quote": law["text"], "applies_to": [original["actor"]],
                 "relevance_type": "specific_match", "confidence": "medium",
                 "notes": "Nonmotor street parking is a source-review question in the frozen curb cell."}],
                 "borderline_excluded": []}
    relevance_ref = put("relevance.json", relevance)
    batch_ref = put("relevance-batch.json", relevance)
    judgment = [
        ("motor vehicle", "Independent legal vehicle and propulsion class review; blueprint is insufficient.",
         ["ru.motor_vehicle", "ru.trailer_or_combination"]),
        ("park any vehicle", "Responsible person, parking purpose and actual stillness require source review.",
         ["drv.standing_or_parked", "kin.time"]),
        ("on any street", "Public street access, jurisdiction and original on-street position require review.",
         ["st.roadway"]),
    ]
    template_id = law["id"] + "@" + original["actor"]
    template = {"template_id": template_id, "law_id": law["id"],
                "actor": original["actor"], "status": "draft", "quote": law["text"],
                "structure": {"activation": {"description": "A person parks a qualifying nonmotor vehicle on a reviewed street during the civil nighttime interval.",
                             "source_clause": "Except for a motor vehicle, no person shall park any vehicle on any street"},
                              "obligation": {"type": "must_not",
                                             "description": "Retain the source-observed continuous duration and compare to the exact statutory threshold without claiming a verdict.",
                                             "source_clause": "for a period of time longer than thirty minutes",
                                             "numeric_conditions": [{"variable": "night_parking_duration_s",
                                                                     "operator": ">", "value": 1800,
                                                                     "unit": "s"}]},
                              "exceptions": [{"description": "Motor vehicle class is excluded; original legal classification required.",
                                              "source_clause": "Except for a motor vehicle"}],
                              "timing": {"description": "Original civil-clock samples inside 01:00–06:00 of any day; endpoints need independent review.",
                                         "source_clause": "between the hours of one a.m. and six a.m. of any day"},
                              "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                                        for phrase, note, _ in judgment]},
                "parameter_refs": [{"name": "night_parking_duration_s", "kind": "subject_behavior",
                                    "range_or_domain": "source-measured continuous seconds below/at/above thirty minutes"},
                                   {"name": "parking_request_duration_s", "kind": "controller",
                                    "range_or_domain": "1799, 1800, 1801 seconds requested"},
                                   {"name": "approach_target_speed_mps", "kind": "controller",
                                    "range_or_domain": "derived 5 m approach divided by stop time"},
                                   {"name": "on_street", "kind": "world_setup",
                                    "range_or_domain": "authored street, pending original review"},
                                   {"name": "qualifying_nonmotor_review", "kind": "world_setup",
                                    "range_or_domain": "source-reviewed, not blueprint inferred"}]}
    template_ref = put("template.json", template)
    judgment_refs = []
    for index, (phrase, note, channels) in enumerate(judgment, start=1):
        requirements = {"observables": [{"name": name, "unit": "structured",
                                           "description": "Source-joined original observation for " + name}
                                          for name in channels],
                        "context_inputs": [{"name": "qualifying_source_review", "unit": "structured",
                                            "description": "Cited original context for " + phrase}],
                        "sweep_dimensions": [], "landmarks": [],
                        "recording_needs": [{"name": name, "unit": "structured",
                                             "description": "Retained source-joined stream for " + name}
                                            for name in channels],
                        "limitations": ["Synthetic software fixtures do not prove original legal or physical classification."]}
        judgment_refs.append(put("judgment-" + str(index) + ".json",
                                 {"template_id": template_id, "phrase": phrase,
                                  "note": note, "status": "draft",
                                  "observable_requirements": requirements}))
    binding = {"cell_id": original["cell_id"], "actor": original["actor"],
               "status": "draft", "established_contexts": [],
               "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": name, "kind": kind,
                                        "range_or_domain": domain,
                                        "used_by_laws": [law["id"]]}
                                       for name, kind, domain in (
                                           ("night_parking_duration_s", "subject_behavior", "source-measured seconds"),
                                           ("parking_request_duration_s", "controller", "1799, 1800, 1801 s"),
                                           ("approach_target_speed_mps", "controller", "derived approach speed"),
                                           ("on_street", "world_setup", "authored street, original review pending"),
                                           ("qualifying_nonmotor_review", "world_setup", "original review pending"))]}
    binding_ref = put("bindings.json", binding)
    base = {"night_parking_duration_s": {"kind": "subject_behavior", "value": None},
            "parking_request_duration_s": {"kind": "controller", "value": None},
            "approach_target_speed_mps": {"kind": "controller", "value": None},
            "on_street": {"kind": "world_setup", "value": True},
            "qualifying_nonmotor_review": {"kind": "world_setup", "value": "requires original source review"}}
    recording = json.loads((HERE / "construction.json").read_text())["recording_description"]
    cases = [{"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Observe curb scene before parking request.",
              "variable_assignments": base, "unresolved_judgment_calls": [x[0] for x in judgment],
              "recording_description": recording}]
    for suffix, target in TARGETS.items():
        values = json.loads(json.dumps(base))
        values["parking_request_duration_s"]["value"] = target
        values["approach_target_speed_mps"]["value"] = APPROACH_DISTANCE_M * RATE_HZ / stop_frame(ASSIGNMENT + "__" + suffix)
        construction = json.loads((HERE / ("construction.json" if suffix == "below_30" else
                                          "cases/" + suffix + "/construction.json")).read_text())
        cases.append({"case_id": ASSIGNMENT + "__" + suffix,
                      "target_law_id": law["id"], "target_type": "boundary_probe",
                      "rationale": "Exact statutory duration bracket on source-reviewed nonmotor parking branch; original acceptance unresolved.",
                      "paired_probe_id": "c229398_duration_boundary",
                      "deliberate_differences": ["parking_request_duration_s", "approach_target_speed_mps"],
                      "variable_assignments": values,
                      "probe": {"primary_variable": "night_parking_duration_s",
                                "comparison_or_standard": "strictly longer than thirty minutes",
                                "target_value_or_branch": suffix, "threshold_ref": "obligation.numeric_conditions[0]",
                                "operator": ">", "unit": "s", "test_value": target},
                      "epsilon_used": {"value": 1, "unit": "s",
                                       "rationale": "One-second engineering bracket around exact legal threshold; no tolerance implied."},
                      "unresolved_judgment_calls": [x[0] for x in judgment],
                      "recording_description": construction["recording_description"]})
    proposal = {"cell_id": original["cell_id"], "actor": original["actor"],
                "status": "draft", "sweep_specs": [{"sweep_id": "nonmotor-parking-source-review",
                "target_law_id": law["id"], "judgment_refs": [{"phrase": phrase, "note": note}
                                                               for phrase, note, _ in judgment],
                "status": "incomplete", "rationale": "Original vehicle, parking activity and street review remains open.",
                "missing_inputs": ["Independent original legal vehicle, purpose and jurisdiction sources."]}],
                "sweeps_expanded": True, "cases": cases}
    cases_ref = put("cases.json", proposal)
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
             "stages": {"relevance_batch": batch_ref, "relevance": relevance_ref,
                        "template": template_ref, "judgment_observables": judgment_refs,
                        "bindings": binding_ref, "cases": cases_ref}}
    put("semantic-index.json", index)
    print(json.dumps({"index_sha256": digest(HERE / "proposals/semantic-index.json"),
                      "selected_cases": len(TARGETS)}))


if __name__ == "__main__":
    build()
