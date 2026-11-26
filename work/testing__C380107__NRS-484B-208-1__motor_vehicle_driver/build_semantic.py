"""Build exact source-bound left-lane/HOV canonical semantic drafts."""

import hashlib
import json
from pathlib import Path
from batch_pipeline.sweeps import expand_sweeps


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
LAW = "NRS-484B-208-1"
CELL = "C380107"
ACTOR = "motor_vehicle_driver"
OUT = HERE / "proposals"


def write(name, value):
    OUT.mkdir(exist_ok=True)
    path = OUT / (name + ".json")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def recording_description():
    channels = []
    for name, unit, method in (
        ("controlled_access_and_lane_geometry", "source record", "reviewed OpenDRIVE, road authority and original lane readback"),
        ("ego_rear_lane_speed_gap", "m, m/s and lane id", "original 20 Hz ego/rear body and lane trace"),
        ("posted_limit_and_knowledge", "m/s and source record", "source-sealed posted limit and knowledge circumstances"),
        ("hov_designation_and_compliance", "source record", "original HOV extent, hours, signs, access, occupancy, category and compliance"),
        ("other_exception_context", "source record", "original city boundary, hazard, traffic, official control and activity context"),
        ("four_synchronized_camera_views", "original frames", "four Native RGB views joined to every original world tick"),
        ("original_sign_exposure_s", "s", "first source-bound posted-limit sign exposure in original 20 Hz trace"),
        ("original_rear_speed_delta_mps", "m/s", "original rear-minus-ego speed at signed-gap crossing"),
        ("original_hov_occupancy_count", "count", "original reviewed occupant identity and count"),
    ):
        channels.append({"name": name, "unit": unit, "method": method,
                         "reference_frame": "reviewed original controlled-access highway and Native world frame",
                         "sampling_rate_hz": 20, "time_window": "all 900 original ticks",
                         "uncertainty": "original physical realization and legal knowledge/HOV qualification pending"})
    return {"channels": channels, "context_inputs": [{"name": "original highway and HOV authority",
             "unit": "source record", "method": "SHA-sealed original site, law and designation packet"}],
            "limitations": ["Engineering speed and gap controls do not define statutory knowledge or overtaking.",
                            "HOV designation alone does not establish actual qualification."]}


def main():
    assignment = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    quote = assignment["law"]["text"]
    template_id = LAW + "@" + ACTOR
    relevance = {"actor": ACTOR, "cell_id": CELL, "status": "draft",
                 "borderline_excluded": [], "relevant_laws": [{"law_id": LAW,
                 "quote": quote, "confidence": "high", "applies_to": [ACTOR]}]}
    write("relevance", relevance)
    write("relevance-batch", relevance)
    parameters = []
    domains = (
        ("hov_designation_request", "world_setup", "none, active, inactive"),
        ("hov_compliance_request", "world_setup", "compliant, noncompliant, unresolved"),
        ("ego_speed_request", "controller", "below or at posted limit"),
        ("rear_encounter_request", "controller", "faster or same-speed rear vehicle"),
        ("ego_response_request", "controller", "remain left or move right"),
        ("exception_context_request", "world_setup", "outside city, inside city, hazard necessity"),
        ("original_ego_speed_mps", "subject_behavior", "measured original ego speed"),
        ("original_rear_gap_m", "subject_behavior", "measured original signed body gap"),
        ("sign_exposure_start_s", "controller", "4, 6, 8 second engineering visibility-onset stations"),
        ("rear_speed_delta_target_mps", "controller", "1, 2, 3 m/s engineering rear-approach stations"),
        ("hov_occupancy_target", "controller", "1, 2, 3 occupant engineering stations"),
        ("original_sign_exposure_s", "subject_behavior", "measured original sign visibility onset"),
        ("original_rear_speed_delta_mps", "subject_behavior", "measured original rear-minus-ego speed"),
        ("original_hov_occupancy_count", "subject_behavior", "measured original occupant count"),
    )
    for name, kind, domain in domains:
        parameters.append({"kind": kind, "name": name,
                           "unit": "m/s" if name in ("original_ego_speed_mps", "rear_speed_delta_target_mps", "original_rear_speed_delta_mps") else
                                   "m" if name == "original_rear_gap_m" else
                                   "s" if name in ("sign_exposure_start_s", "original_sign_exposure_s") else
                                   "count" if name in ("hov_occupancy_target", "original_hov_occupancy_count") else "categorical",
                           "range_or_domain": domain})
    judgments = [{"phrase": "knows, or reasonably should know",
                  "note": "Source-backed circumstances and original speed are retained; legal knowledge remains unresolved."},
                 {"phrase": "being overtaken in that lane from the rear",
                  "note": "Original rear identity, speed, lane and signed-gap history need independent review."},
                 {"phrase": "complies with the requirements to travel in such a lane",
                  "note": "Designation, hours, occupancy, vehicle category, signs and access require original authority and review."}]
    structure = {"activation": {"source_clause": "on a controlled-access highway which has two or more clearly marked lanes for traveling in the same direction"},
                 "obligation": {"source_clause": "may not continue to operate a motor vehicle in the extreme left lane"},
                 "timing": {"source_clause": "if the driver knows, or reasonably should know, that he or she is traveling at a rate of speed which is less than the posted speed limit"},
                 "exceptions": [{"source_clause": "The requirements of subsection 1 do not apply"}],
                 "judgment_calls_needed": judgments}
    write("template", {"actor": ACTOR, "law_id": LAW, "parameter_refs": parameters,
                       "quote": quote, "status": "draft", "template_id": template_id,
                       "structure": structure})
    common = {"context_inputs": [{"name": "original highway and HOV authority",
                                   "description": "SHA-sealed original site and designation packet",
                                   "unit": "source record"}],
              "landmarks": [], "limitations": ["No legal threshold inferred from engineering controls."],
              "observables": [{"name": "ego_rear_lane_speed_gap", "unit": "m, m/s and lane id",
                               "description": "Original 20 Hz ego/rear identity, lane, speed and signed gap"},
                              {"name": "hov_designation_and_compliance", "unit": "source record",
                               "description": "Original HOV designation and actual compliance evidence"}],
              "recording_needs": [{"name": "four_synchronized_camera_views", "unit": "original frames",
                                   "description": "Original four-view identity and context review"}],
              "sweep_dimensions": []}
    sweep_observables = ("original_sign_exposure_s", "original_rear_speed_delta_mps", "original_hov_occupancy_count")
    sweep_units = ("s", "m/s", "count")
    for i, judgment in enumerate(judgments):
        requirements = json.loads(json.dumps(common))
        requirements["sweep_dimensions"] = [{"name": sweep_observables[i], "unit": sweep_units[i],
                                              "description": "source-bound original 20 Hz measurement"}]
        write("judgment-" + str(i), {"note": judgment["note"], "phrase": judgment["phrase"],
                                    "observable_requirements": requirements, "status": "draft",
                                    "template_id": template_id})
    write("bindings", {"actor": ACTOR, "cell_id": CELL, "context_refs": [],
                       "fixed_parameters": [], "law_refs": [{"binding_kind": "direct", "template_id": template_id}],
                       "status": "draft", "variable_parameters": [dict(p, used_by_laws=[LAW]) for p in parameters]})
    description = recording_description()
    def assignments(case):
        values = [case.get(name) for name, _, _ in domains[:6]] + [None, None, 6.0, 2.0, 2, None, None, None]
        return {p["name"]: {"kind": p["kind"], "unit": p["unit"], "value": value}
                for p, value in zip(parameters, values)}
    baseline = {"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Shared source and capture definition; no separate recording.",
                "recording_description": description, "unresolved_judgment_calls": judgments,
                "variable_assignments": assignments(plan["cases"][0])}
    selected = []
    for case in (c for c in plan["cases"] if c.get("variant")):
        selected.append({"case_id": case["case_id"], "target_law_id": LAW,
                         "target_type": "boundary_probe",
                         "rationale": "Exact left-lane/HOV encounter or exception control; legal interpretation unresolved.",
                         "probe": {"comparison_or_standard": "source-bound original observation",
                                   "primary_variable": "ego_speed_request",
                                   "target_value_or_branch": case["variant"]},
                         "paired_probe_id": "left_lane_hov_exception",
                         "deliberate_differences": list(name for name, _, _ in domains[:6]),
                         "recording_description": description,
                         "unresolved_judgment_calls": judgments,
                         "variable_assignments": assignments(case)})
    sweep_specs = []
    for i, (suffix, variable, observable, unit, low, high, spacing) in enumerate((
        ("sign_exposure", "sign_exposure_start_s", "original_sign_exposure_s", "s", 4.0, 8.0, 2.0),
        ("rear_speed_delta", "rear_speed_delta_target_mps", "original_rear_speed_delta_mps", "m/s", 1.0, 3.0, 1.0),
        ("hov_occupancy", "hov_occupancy_target", "original_hov_occupancy_count", "count", 1, 3, 1),
    )):
        sweep_specs.append({"sweep_id": ASSIGNMENT + "__" + suffix,
                            "target_law_id": LAW, "judgment_refs": [judgments[i]],
                            "status": "complete", "mode": "one_dimensional", "landmarks": [],
                            "rationale": "Three bounded source-gated engineering stations sample physical coverage without defining a legal cutoff.",
                            "recording_description": description,
                            "variable_assignments": assignments(plan["cases"][0]),
                            "axes": [{"variable": variable, "observable": observable, "unit": unit,
                                      "min": low, "max": high, "spacing": spacing,
                                      "measurement": {"method": "source-bound original 20 Hz readback",
                                                      "time_window": "all 900 original ticks", "statistic": "first"},
                                      "range_rationale": "Finite engineering coverage around an operational setpoint; no statutory threshold inferred.",
                                      "spacing_rationale": "Three distinguishable local controller stations.",
                                      "feasibility_evidence": "Source-gated controls and original readback specified; Native realization awaits local review."}]})
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
                       "judgment_observables": ["judgment-0", "judgment-1", "judgment-2"],
                       "cases": ["cases"]}.items():
        refs = [{"path": "proposals/" + name + ".json",
                 "sha256": hashlib.sha256((OUT / (name + ".json")).read_bytes()).hexdigest()}
                for name in names]
        stages[key] = refs if key == "judgment_observables" else refs[0]
    write("semantic-index", {"format": "worker-semantic-delivery",
                             "assignment_id": ASSIGNMENT, "stages": stages})
    print("Built", len(cases["cases"]) - 1, "selected semantic cases and", len(plan["comparisons"]), "comparisons")


if __name__ == "__main__":
    main()
