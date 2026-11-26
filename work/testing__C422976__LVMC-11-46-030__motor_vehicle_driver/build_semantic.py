"""Build canonical draft stages for the exact school pedestrian-lane law."""

import hashlib
import json
from pathlib import Path

from package_contract import ACTOR, CASES, CELL, LAW, recording_description
from school_lane_controls import ASSIGNMENT, VARIANTS
from batch_pipeline.sweeps import expand_sweeps


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "proposals"


def write(name, value):
    OUT.mkdir(exist_ok=True)
    (OUT / (name + ".json")).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    source = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    quote = source["law"]["text"]
    template_id = LAW + "@" + ACTOR
    relevance = {"actor": ACTOR, "cell_id": CELL, "status": "draft",
                 "borderline_excluded": [], "relevant_laws": [{"law_id": LAW,
                 "quote": quote, "confidence": "high", "applies_to": [ACTOR]}]}
    write("relevance", relevance)
    write("relevance-batch", relevance)
    parameters = [
        {"kind": "controller", "name": "stop_distance_target_ft", "unit": "ft",
         "range_or_domain": "49, 50, 51 foot engineering station targets around the stated fifty-foot number"},
        {"kind": "world_setup", "name": "warning_kind", "unit": "categorical",
         "range_or_domain": "human, device, none, human present without child warning"},
        {"kind": "world_setup", "name": "release_kind", "unit": "categorical",
         "range_or_domain": "go signal, person departure, signal raised, continued presence, none"},
        {"kind": "controller", "name": "ego_response", "unit": "categorical",
         "range_or_domain": "stop then proceed, wait, premature proceed, travel"},
        {"kind": "subject_behavior", "name": "original_stop_distance_ft", "unit": "ft",
         "range_or_domain": "measured original body-reference to nearest-side distance"},
        {"kind": "subject_behavior", "name": "original_release_readback", "unit": "source observation",
         "range_or_domain": "measured original warning, go gesture, departure and device state"},
        {"kind": "controller", "name": "warning_onset_s", "unit": "s",
         "range_or_domain": "4, 6, 8 seconds from episode start for bounded engineering sampling"},
        {"kind": "controller", "name": "departure_onset_s", "unit": "s",
         "range_or_domain": "10, 12, 14 seconds from episode start for bounded engineering sampling"},
        {"kind": "subject_behavior", "name": "original_warning_onset_s", "unit": "s",
         "range_or_domain": "original frame where stationed actor first gives a child-crossing warning"},
        {"kind": "subject_behavior", "name": "original_departure_onset_s", "unit": "s",
         "range_or_domain": "original frame where warning person begins departing the reviewed locality"},
    ]
    judgments = [
        {"phrase": "children are about to cross or are crossing the street",
         "note": "Child-crossing warning and actual child status require distinct original evidence."},
        {"phrase": "has left the locality",
         "note": "The locality boundary is source and legal review dependent; motion alone does not decide it."},
    ]
    structure = {"activation": {"source_clause": "where any signal device, flagman or other person is stationed, giving warning that children are about to cross or are crossing the street"},
                 "obligation": {"source_clause": "fail to stop not less than fifty feet from the nearest side of a school pedestrian lane"},
                 "timing": {"source_clause": "proceed until such signal has stopped, raised, or been removed, or the flagman or person stationed at such pedestrian lane has given a signal to go, or has left the locality"},
                 "exceptions": [], "judgment_calls_needed": judgments}
    write("template", {"actor": ACTOR, "law_id": LAW, "parameter_refs": parameters,
                       "quote": quote, "status": "draft", "template_id": template_id,
                       "structure": structure})
    common = {"context_inputs": [{"name": "municipal jurisdiction and reviewed school-lane authority",
                                  "description": "SHA-sealed original site, map, geometry and actor packet",
                                  "unit": "source record"}],
              "landmarks": [], "limitations": ["Engineering station targets and original observations do not decide legal compliance."],
              "observables": [{"name": "human_warning_children_and_release",
                               "description": "20 Hz original human warning, children, go gesture and departure readback",
                               "unit": "source observation"},
                              {"name": "device_warning_and_release",
                               "description": "20 Hz original device warning and raised/stopped/removed state",
                               "unit": "source observation"}],
              "recording_needs": [{"name": "human_warning_children_and_release",
                                   "description": "Original human and child bodies plus four-camera gesture review",
                                   "unit": "source observation"}],
              "sweep_dimensions": []}
    for i, judgment in enumerate(judgments):
        requirements = json.loads(json.dumps(common))
        observable = "original_warning_onset_s" if i == 0 else "original_departure_onset_s"
        requirements["sweep_dimensions"] = [{"name": observable, "unit": "s",
                                             "description": "original 20 Hz actor-state onset time"}]
        write("judgment-" + str(i), {"note": judgment["note"], "phrase": judgment["phrase"],
                                    "observable_requirements": requirements, "status": "draft",
                                    "template_id": template_id})
    write("bindings", {"actor": ACTOR, "cell_id": CELL, "context_refs": [],
                       "fixed_parameters": [], "law_refs": [{"binding_kind": "direct", "template_id": template_id}],
                       "status": "draft", "variable_parameters": [dict(p, used_by_laws=[LAW]) for p in parameters]})
    description = recording_description()
    def assignments(variant):
        values = (variant.stop_target_ft, variant.warning, variant.release,
                  variant.response, None, None, 6.0, 12.0, None, None)
        return {p["name"]: {"kind": p["kind"], "unit": p["unit"], "value": value}
                for p, value in zip(parameters, values)}
    baseline = {"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Shared source and capture definition; no separate recording.",
                "recording_description": description, "unresolved_judgment_calls": judgments,
                "variable_assignments": assignments(VARIANTS[0])}
    selected = []
    for variant in VARIANTS:
        selected.append({"case_id": ASSIGNMENT + "__" + variant.suffix,
                         "target_law_id": LAW, "target_type": "boundary_probe",
                         "rationale": "Source-gated exact school-lane warning, stop and release comparison.",
                         "probe": {"comparison_or_standard": "original source observations; legal verdict unresolved",
                                   "primary_variable": "stop_distance_target_ft" if variant.stop_target_ft in (49, 50)
                                                       else "release_kind",
                                   "target_value_or_branch": variant.suffix},
                         "paired_probe_id": "school_lane_stop_warning_release",
                         "deliberate_differences": ["stop_distance_target_ft", "warning_kind", "release_kind", "ego_response"],
                         "recording_description": description,
                         "unresolved_judgment_calls": judgments,
                         "variable_assignments": assignments(variant)})
    sweep_specs = []
    for i, (suffix, controller, observable, low, high) in enumerate((
        ("child_warning_onset", "warning_onset_s", "original_warning_onset_s", 4.0, 8.0),
        ("person_departure_onset", "departure_onset_s", "original_departure_onset_s", 10.0, 14.0),
    )):
        sweep_specs.append({"sweep_id": ASSIGNMENT + "__" + suffix,
                            "target_law_id": LAW, "judgment_refs": [judgments[i]],
                            "status": "complete", "mode": "one_dimensional", "landmarks": [],
                            "rationale": "Three source-gated actor timing stations sample physical coverage; legal phrase remains unresolved.",
                            "recording_description": description,
                            "variable_assignments": assignments(VARIANTS[0]),
                            "axes": [{"variable": controller, "observable": observable, "unit": "s",
                                      "min": low, "max": high, "spacing": 2.0,
                                      "measurement": {"method": "first source-bound actor-state transition in original 20 Hz capture",
                                                      "time_window": "all 900 original ticks", "statistic": "first"},
                                      "range_rationale": "Bounded timing coverage within the 45-second episode; stations are not legal thresholds.",
                                      "spacing_rationale": "Three distinguishable controller stations; actual timing requires original capture.",
                                      "feasibility_evidence": "Source-gated schedule controller and CPU tests; Native realization requires original review."}]})
    cases = {"actor": ACTOR, "cell_id": CELL, "cases": [baseline, *selected],
             "comparisons": [{k: c[k] for k in ("comparison_id", "case_ids", "fixed_conditions", "deliberate_differences")}
                             for c in plan["comparisons"]],
             "source_assignment": "inputs/" + ASSIGNMENT + "/assignment.json",
             "source_law_text": quote, "status": "draft", "sweep_specs": sweep_specs,
             "sweeps_expanded": False}
    expand_sweeps(cases, templates=[json.loads((OUT / "template.json").read_text())],
                  bindings=json.loads((OUT / "bindings.json").read_text()))
    write("cases", cases)
    stages = {}
    for key, names in {"relevance": ["relevance"], "relevance_batch": ["relevance-batch"],
                       "template": ["template"], "bindings": ["bindings"],
                       "judgment_observables": ["judgment-0", "judgment-1"],
                       "cases": ["cases"]}.items():
        refs = [{"path": "proposals/" + name + ".json",
                 "sha256": hashlib.sha256((OUT / (name + ".json")).read_bytes()).hexdigest()}
                for name in names]
        stages[key] = refs if key == "judgment_observables" else refs[0]
    write("semantic-index", {"format": "worker-semantic-delivery",
                             "assignment_id": ASSIGNMENT, "stages": stages})
    print("Built nine exact school-lane semantic draft cases and eight comparisons")


if __name__ == "__main__":
    main()
