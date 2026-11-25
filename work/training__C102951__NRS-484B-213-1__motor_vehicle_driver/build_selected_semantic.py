"""Build source-faithful draft semantic stages for the three distance probes."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
PROPOSALS = HERE / "proposals"
LAW_ID = ASSIGNMENT["law_id"]
ACTOR = ASSIGNMENT["actor"]
TEMPLATE_ID = f"{LAW_ID}@{ACTOR}"
QUOTE = ASSIGNMENT["law"]["text"]


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return {"path": f"proposals/{name}", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def observable(name, unit, description):
    return {"name": name, "unit": unit, "description": description}


def main():
    relevance = {
        "cell_id": ASSIGNMENT["cell_id"], "actor": ACTOR, "status": "draft",
        "relevant_laws": [{
            "law_id": LAW_ID, "quote": QUOTE, "applies_to": [ACTOR],
            "relevance_type": "specific_match", "confidence": "low",
            "notes": "Exact left-of-center passing clause applies; actual highway geometry, visibility and noninterference require original review."
        }], "borderline_excluded": []
    }
    references = {}
    references["relevance_batch"] = write("relevance_batch.json", relevance)
    references["relevance"] = write("relevance.json", relevance)
    judgments = [
        {"phrase": "clearly visible", "note": "Original hill-crest sightline and driver-reference pixels require independent review."},
        {"phrase": "sufficient distance ahead to permit such overtaking and passing to be completely made without interfering with the safe operation of any vehicle approaching from the opposite direction or any vehicle overtaken", "note": "Preserve actual pass completion and separate approaching and overtaken vehicle responses; no numeric legal cutoff is inferred."},
    ]
    template = {
        "template_id": TEMPLATE_ID, "law_id": LAW_ID, "actor": ACTOR,
        "status": "draft", "quote": QUOTE,
        "structure": {
            "activation": {"description": "Driver uses left side of center on a two-lane, two-directional highway to overtake a same-direction vehicle", "numeric_conditions": []},
            "obligation": {"type": "must", "description": "Do not make the left-of-center pass unless the statutory visibility, clear distance and noninterference conditions hold", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Measure the full original pass, approaching vehicle and overtaken vehicle timelines", "numeric_conditions": []},
            "judgment_calls_needed": judgments,
        },
        "parameter_refs": [
            {"name": "requested_oncoming_distance_m", "kind": "controller", "range_or_domain": "70, 120 and 170 m requested physical samples; no legal threshold"},
            {"name": "actual_entry_oncoming_body_gap_m", "kind": "subject_behavior", "range_or_domain": "source-measured m at original left-of-center entry"},
        ],
    }
    references["template"] = write("template.json", template)
    requirements = [
        {
            "observables": [
                observable("driver_eye_sightline", "m,visibility_flag", "Original eye-reference sightline and image evidence across the full pass."),
                observable("st.sight_distance", "m", "Shared vehicle-reference proxy, kept distinct from actual driver perception."),
            ],
            "context_inputs": [observable("roadway_geometry", "lane_count,direction,highway_status,centerline,crest_profile", "Original two-lane highway and crest geometry with centerline." )],
            "sweep_dimensions": [observable("measured_clear_oncoming_distance", "m", "Original measured gap used to assess requested physical coverage, never a legal threshold." )],
            "landmarks": [],
            "recording_needs": [observable("native_actor_poses", "structured", "Retain synchronized original four-camera pixels, Native poses and frame map.")],
            "limitations": ["Synthetic sightline proxies and pixels do not establish actual legal visibility."],
        },
        {
            "observables": [
                observable("measured_clear_oncoming_distance", "m", "Original entry body gap and full approach path."),
                observable("pass_completion_and_interference", "s,m,flag", "Original complete-pass path and interaction observations."),
                observable("approaching_vehicle_response", "m/s,m/s^2", "Separate original approaching vehicle trajectory and response."),
                observable("overtaken_vehicle_response", "m/s,m/s^2", "Separate original overtaken vehicle trajectory and response."),
            ],
            "context_inputs": [observable("roadway_geometry", "lane_count,direction,highway_status,centerline,crest_profile", "Original road and centerline context.")],
            "sweep_dimensions": [observable("measured_clear_oncoming_distance", "m", "Physical coverage observation; no legal threshold is inferred.")],
            "landmarks": [],
            "recording_needs": [observable("native_actor_poses", "structured", "Retain original actor, road, sightline, frame-map and four-camera sources.")],
            "limitations": ["No 70, 120 or 170 m value is a legal sufficiency or safe-operation threshold."],
        },
    ]
    references["judgment_observables"] = [write(f"judgment_observables_{i}.json", {
        "template_id": TEMPLATE_ID, "phrase": judgment["phrase"], "note": judgment["note"],
        "status": "draft", "observable_requirements": requirements[i]
    }) for i, judgment in enumerate(judgments)]
    binding = {
        "cell_id": ASSIGNMENT["cell_id"], "actor": ACTOR, "status": "draft",
        "established_contexts": [{"name": "C102951 hill crest and same-direction pass", "source": "Frozen catalog cell; physical highway and motion require original review."}],
        "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [
            {"name": "requested_oncoming_distance_m", "kind": "controller", "range_or_domain": "70,120,170 m physical samples", "used_by_laws": [LAW_ID]},
            {"name": "actual_entry_oncoming_body_gap_m", "kind": "subject_behavior", "range_or_domain": "original-source m", "used_by_laws": [LAW_ID]},
            {"name": "measured_clear_oncoming_distance", "kind": "subject_behavior", "range_or_domain": "original-source m", "used_by_laws": [LAW_ID]},
        ],
    }
    references["bindings"] = write("bindings.json", binding)
    cases = json.loads((PROPOSALS / "cases.json").read_text())
    cases["cases"] = [c for c in cases["cases"] if c["target_type"] != "baseline"]
    for c in cases["cases"]:
        c["variable_assignments"]["measured_clear_oncoming_distance"] = {"kind": "subject_behavior", "unit": "m", "value": None}
    baseline = deepcopy(next(c for c in cases["cases"] if c["case_id"].endswith("__120")))
    baseline["case_id"] = HERE.name + "__baseline_reference"
    baseline["target_type"] = "baseline"
    baseline["rationale"] = "Shared 120 m planning reference; reuse selected 120 m source, no additional recording."
    baseline["reuse_case_id"] = HERE.name + "__120"
    baseline.pop("paired_probe_id", None)
    cases["cases"].insert(0, baseline)
    for c in cases["cases"][1:]:
        c["sweep_id"] = "C102951-passing-distance"
        c["unresolved_judgment_calls"] = [j["phrase"] for j in judgments]
        c["sweep_spec_version"] = None
        c["sweep_point"] = {"requested_oncoming_distance_m": float(c["variable_assignments"]["requested_oncoming_distance_m"]["value"])}
    cases["cases"][1:] = [next(c for c in cases["cases"][1:] if c["sweep_point"]["requested_oncoming_distance_m"] == v) for v in (70.0, 170.0, 120.0)]
    spec = {
        "sweep_id": "C102951-passing-distance", "target_law_id": LAW_ID,
        "judgment_refs": judgments, "rationale": "Physical comparison grid for requested gap; not a statutory numeric cutoff.",
        "status": "complete", "mode": "one_dimensional",
        "axes": [{
            "variable": "requested_oncoming_distance_m", "observable": "measured_clear_oncoming_distance", "unit": "m",
            "min": 70, "max": 170, "spacing": 50,
            "range_rationale": "Frozen requested comparison spans 70, 120 and 170 m.",
            "spacing_rationale": "Frozen three-value physical comparison step is 50 m.",
            "feasibility_evidence": "Three source-bound 600-frame selected fixture packets and six exact offline/compatibility receipts.",
            "measurement": {"method": "Read configured setpoint and compare it with original Native entry gap", "time_window": "left-of-center entry in full 30 s attempt", "statistic": "first"},
        }],
        "landmarks": [], "recording_description": deepcopy(cases["cases"][1]["recording_description"]),
    }
    from batch_pipeline.store import digest
    spec["spec_version"] = digest(spec)
    spec["planned_case_count"] = 3
    spec["selection_order"] = [c["case_id"] for c in cases["cases"][1:]]
    for c in cases["cases"][1:]:
        c["sweep_spec_version"] = spec["spec_version"]
    cases["sweep_specs"] = [spec]
    cases["sweeps_expanded"] = True
    references["cases"] = write("cases.json", cases)
    write("semantic-index.json", {
        "assignment_id": HERE.name, "format": "worker-semantic-delivery", "status": "draft", "stages": references
    })


if __name__ == "__main__":
    main()
