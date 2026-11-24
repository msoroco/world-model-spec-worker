"""Build source-bound draft semantic stages for NRS 484B.600(1)(a).

These are planning artifacts. They intentionally assert no legal cutoff,
physical realization, or accepted recording equivalence.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
ASSIGNMENT_ID = "training__C230259__NRS-484B-600-1a__motor_vehicle_driver"
assignment = json.loads((ROOT / "inputs" / ASSIGNMENT_ID / "assignment.json").read_text())
law = assignment["law"]
law_id = law["id"]
actor = assignment["actor"]
cell_id = assignment["cell_id"]
template_id = law_id + "@" + actor
quote = law["text"]


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


relevance = {
    "cell_id": cell_id, "actor": actor, "status": "draft",
    "relevant_laws": [{"law_id": law_id, "quote": quote,
                       "applies_to": [actor], "relevance_type": "specific_match",
                       "confidence": "high",
                       "notes": "Road travel by the assigned driver invokes the speed duty; actual reasonableness requires observed conditions and independent judgment."}],
    "borderline_excluded": [],
}
write("relevance-batch.json", relevance)
write("relevance.json", relevance)

judgment = {"phrase": "reasonable or proper",
            "note": "Keep actual speed and contemporaneous traffic, surface, width, weather and other highway conditions separate; no numeric legal cutoff is supplied."}
template = {
    "template_id": template_id, "law_id": law_id, "actor": actor,
    "quote": quote, "status": "draft",
    "structure": {
        "law_id": law_id,
        "activation": {"condition": "a person drives or operates a vehicle of any kind or character", "numeric_conditions": []},
        "obligation": {"type": "speed_duty", "description": "rate of speed must not be greater than is reasonable or proper with due regard for the named conditions", "source_clause": quote, "numeric_conditions": []},
        "exceptions": [],
        "timing": {"description": "during observed driving, joining speed to contemporaneous conditions", "numeric_conditions": []},
        "judgment_calls_needed": [judgment],
    },
    "parameter_refs": [
        {"name": "ego_speed", "kind": "subject_behavior", "range_or_domain": "measured original Native speed, unknown until capture"},
        {"name": "speed_controller_target_mps", "kind": "controller", "range_or_domain": "authored speed requests in m/s; not measured speed"},
        {"name": "traffic_configuration", "kind": "world_setup", "range_or_domain": "fixed participant identities, trajectories and traffic controls"},
        {"name": "road_surface_width_weather", "kind": "world_setup", "range_or_domain": "fixed pavement, lane width, weather and visibility setup with measured readback"},
    ],
}
write("template.json", template)

observable = {
    "template_id": template_id, "phrase": judgment["phrase"], "note": judgment["note"], "status": "draft",
    "observable_requirements": {
        "observables": [
            {"name": "ego_speed", "unit": "m/s", "description": "original frame-joined vehicle velocity magnitude, retaining full time series"},
            {"name": "surrounding_traffic", "unit": "structured", "description": "participant identity, position, velocity, interactions and occupancy joined by original frame"},
        ],
        "context_inputs": [
            {"name": "road_surface_width_weather", "unit": "structured", "description": "surveyed surface and width and measured weather, visibility, friction and geometry"},
            {"name": "traffic_configuration", "unit": "structured", "description": "authored participant and control setup; check actual realization"},
        ],
        "sweep_dimensions": [{"name": "speed_controller_target_mps", "unit": "m/s", "description": "engineering speed request axis; actual speed is a separate observed channel"}],
        "landmarks": [],
        "recording_needs": [
            {"name": "native_motion_and_participants", "unit": "structured", "description": "original Native frame map, ego and participant motion with join/readback"},
            {"name": "source_camera_views", "unit": "video", "description": "four synchronized original source-camera videos and per-frame decode map"},
        ],
        "limitations": ["The statute supplies no numeric boundary for reasonable or proper speed.",
                        "Requested controller speed cannot substitute for measured Native speed or legal judgment.",
                        "Accepted recording membership alone cannot establish coverage of contemporaneous conditions."],
    },
}
write("judgment-observables.json", observable)

bindings = {
    "cell_id": cell_id, "actor": actor, "status": "draft",
    "established_contexts": ["Frozen road/travel/other_vehicle cell supports a speed-conditions study; original geometry and participant realization remain unverified."],
    "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
    "context_refs": [], "fixed_parameters": [],
    "variable_parameters": [
        {"name": "ego_speed", "kind": "subject_behavior", "range_or_domain": "original Native speed time series; never assigned", "used_by_laws": [law_id]},
        {"name": "speed_controller_target_mps", "kind": "controller", "range_or_domain": "8, 12, 16 and 20 m/s requested for a controlled engineering sweep", "used_by_laws": [law_id]},
        {"name": "traffic_configuration", "kind": "world_setup", "range_or_domain": "fixed participant/control configuration and measured readback", "used_by_laws": [law_id]},
        {"name": "road_surface_width_weather", "kind": "world_setup", "range_or_domain": "fixed roadway and weather configuration and measured readback", "used_by_laws": [law_id]},
    ],
}
write("bindings.json", bindings)

channels = []
for name, unit, method in [
    ("ego_speed", "m/s", "original Native ego velocity magnitude, frame joined to controller and cameras"),
    ("surrounding_traffic", "structured", "original Native participant pose, velocity and interactions"),
    ("native_motion_and_participants", "structured", "original Native frame map and all participant readbacks"),
    ("source_camera_views", "video", "four original synchronized source-camera videos, decoded with frame IDs"),
]:
    channels.append({"name": name, "unit": unit, "sampling_rate_hz": 20,
                     "method": method, "time_window": "at least 30 s / at least 600 joined frames",
                     "reference_frame": "original Native frame and surveyed map",
                     "uncertainty": "50 ms sampling; original source integrity and physical readback pending"})
recording = {
    "channels": channels,
    "context_inputs": [
        {"name": "traffic_configuration", "unit": "structured", "method": "authored setup and original Native participant/control readback"},
        {"name": "road_surface_width_weather", "unit": "structured", "method": "surveyed map and original Native weather/surface readback"},
    ],
    "limitations": ["No physical or legal outcome follows from the requested speed.",
                    "Existing accepted recordings must be reviewed before requesting duplicate capture."],
}


def assignments(target):
    return {
        "ego_speed": {"kind": "subject_behavior", "value": None, "unit": "m/s", "source": "original Native motion pending"},
        "speed_controller_target_mps": {"kind": "controller", "value": target, "unit": "m/s", "source": "author requested engineering setpoint"},
        "traffic_configuration": {"kind": "world_setup", "value": "fixed_C230259_participants_controls", "unit": "structured", "source": "frozen cell; original realization pending"},
        "road_surface_width_weather": {"kind": "world_setup", "value": "fixed_C230259_surface_width_weather", "unit": "structured", "source": "frozen cell; original realization pending"},
    }


baseline = {"case_id": ASSIGNMENT_ID + "__semantic_baseline", "target_law_id": None,
            "target_type": "baseline", "rationale": "Shared planning baseline with no asserted speed outcome.",
            "variable_assignments": assignments(8), "recording_description": recording,
            "unresolved_judgment_calls": [judgment["phrase"]]}
cases = [baseline]
for target in (8, 12, 16, 20):
    cases.append({
        "case_id": ASSIGNMENT_ID + "__" + str(target),
        "target_law_id": law_id, "target_type": "judgment_sweep",
        "rationale": "Controlled requested speed comparison, holding roadway, weather and traffic setup fixed; physical speed and reasonableness unresolved.",
        "variable_assignments": assignments(target), "recording_description": recording,
        "unresolved_judgment_calls": [judgment["phrase"]],
        "paired_probe_id": ASSIGNMENT_ID + "__speed_pair",
        "deliberate_differences": ["speed_controller_target_mps"],
        "probe": {"primary_variable": "speed_controller_target_mps",
                  "comparison_or_standard": "measured original speed in contemporaneous conditions, without numeric legal boundary",
                  "target_value_or_branch": target},
    })
case_stage = {"cell_id": cell_id, "actor": actor, "status": "draft", "cases": cases,
              "sweep_specs": [{"sweep_id": "C230259-speed-conditions", "target_law_id": law_id,
                               "judgment_refs": [judgment], "rationale": "Actual speed versus contemporaneous conditions, source-bound and without legal cutoff.",
                               "status": "incomplete", "missing_inputs": ["Original Native feasibility and controller-to-measured-speed mapping for the full proposed range", "Source review of accepted recording equivalence and unmet full traffic/weather branches", "Four-camera original capture and independent legal judgment protocol"]}]}
write("cases.json", case_stage)
