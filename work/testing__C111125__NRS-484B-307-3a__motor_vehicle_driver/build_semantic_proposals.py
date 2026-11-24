"""Author source-faithful draft semantic stages for the dual-green branch."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver"
LAW = "NRS-484B-307-3a"
ACTOR = "motor_vehicle_driver"
TEMPLATE_ID = LAW + "@" + ACTOR
PHRASES = [
    ("such other movement as is permitted by the circular green signal",
     "Straight movement needs source-backed circular-green and local restriction review."),
    ("yield the right-of-way", "The source supplies no numeric yielding boundary."),
    ("lawfully within an adjacent crosswalk",
     "Lawful pedestrian presence needs independent crossing-control context."),
    ("lawfully using the intersection",
     "Lawful other-traffic use needs independent approach-control context."),
]
VARIABLES = [
    ("dual_aspect_setup", "world_setup", "source-observed circular green and green turn arrow facing ego"),
    ("participant_kind", "world_setup", "none, motor vehicle, or pedestrian"),
    ("participant_presence_at_exhibition", "world_setup", "clear, intersection, adjacent crosswalk, or outside then entering"),
    ("commanded_straight_path", "controller", "straight route through the surveyed intersection"),
]


def write(name, obj):
    path = ROOT / "proposals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def recording_description():
    def channel(name, method):
        return {"name": name, "unit": "structured record", "sampling_rate_hz": 20,
                "method": method, "time_window": "exhibition through intersection clearance",
                "reference_frame": "original Native frame and world time",
                "uncertainty": "20 Hz sample spacing and surveyed geometry precision"}
    return {
        "channels": [
            channel("signal_head_history", "Independent frame-matched official-head aspect packets and original lamp image"),
            channel("ego_body_history", "Original ego pose, heading, speed and intersection entry"),
            channel("vehicle_body_history", "Original other-vehicle pose and identity, if present"),
            channel("pedestrian_body_history", "Original pedestrian pose and identity, if present"),
            channel("intersection_geometry", "Source-sealed surveyed intersection polygon joined to frames"),
            channel("crosswalk_geometry", "Source-sealed adjacent crosswalk polygon joined to frames"),
            channel("lawful_presence_context", "Original per-participant control and lawful-use packet references"),
            channel("original_lamp_pixels", "Source-sealed original image showing the official facing head"),
        ],
        "context_inputs": [{"name": "site_source_survey", "unit": "structured record",
                            "method": "Independent Native map, head, route and movement-restriction review"}],
        "limitations": [
            "CARLA Green state alone does not establish simultaneous circular and arrow lamps.",
            "Physical occupancy does not itself determine lawful use, right of way, or permission.",
        ],
    }


def variable_assignments(suffix):
    states = {
        "dual_clear": ("none", "clear"),
        "dual_vehicle_present": ("motor_vehicle", "intersection"),
        "dual_pedestrian_present": ("pedestrian", "adjacent_crosswalk"),
        "dual_pedestrian_late": ("pedestrian", "outside_then_entering"),
    }
    kind, region = states[suffix]
    values = {"dual_aspect_setup": "source_observed_circular_green_with_turn_arrow",
              "participant_kind": kind, "participant_presence_at_exhibition": region,
              "commanded_straight_path": "straight"}
    return {name: {"kind": type_, "value": values[name], "note": "Physical setup target; original source decides realization"}
            for name, type_, _ in VARIABLES}


def build():
    original = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    text = original["law"]["text"]
    relevance = {
        "cell_id": "C111125", "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": text,
                           "applies_to": [ACTOR], "relevance_type": "direct facing dual-green signal and straight movement",
                           "confidence": "high", "notes": "The assigned cell is straight travel; actual dual aspect and movement permission require original review."}],
        "borderline_excluded": [],
    }
    refs = {"relevance_batch": write("relevance_batch.json", relevance),
            "relevance": write("relevance.json", relevance)}
    template = {
        "template_id": TEMPLATE_ID, "law_id": LAW, "actor": ACTOR, "quote": text,
        "structure": {
            "law_id": LAW,
            "activation": {"condition": "Vehicular traffic faces circular green with a simultaneous green turn arrow.", "numeric_conditions": []},
            "obligation": {"description": "Other movement permitted by circular green is conditional; traffic must yield to lawfully present pedestrians and intersection traffic.", "type": "may_with_yield_duty", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Lawful-use context is tied to the time the dual signal is exhibited.", "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note in PHRASES],
        },
        "parameter_refs": [{"name": name, "kind": type_, "range_or_domain": domain}
                           for name, type_, domain in VARIABLES],
    }
    refs["template"] = write("template.json", template)
    judgment_refs = []
    for index, (phrase, note) in enumerate(PHRASES, 1):
        observables = [
            {"name": "signal_head_history", "unit": "structured record", "description": "Original dual-aspect official-head exhibition history."},
            {"name": "ego_body_history", "unit": "structured record", "description": "Original ego approach and intersection crossing."},
            {"name": "vehicle_body_history", "unit": "structured record", "description": "Original other-traffic occupancy and motion."},
            {"name": "pedestrian_body_history", "unit": "structured record", "description": "Original adjacent-crosswalk pedestrian occupancy and motion."},
            {"name": "original_lamp_pixels", "unit": "structured record", "description": "Original image evidence for the official facing head."},
        ]
        contexts = [
            {"name": "intersection_geometry", "unit": "structured record", "description": "Surveyed intersection boundary."},
            {"name": "crosswalk_geometry", "unit": "structured record", "description": "Surveyed adjacent crosswalk."},
            {"name": "lawful_presence_context", "unit": "structured record", "description": "Independent participant control and lawful-use source."},
            {"name": "site_source_survey", "unit": "structured record", "description": "Official head, straight route and movement-restriction source."},
        ]
        judgment_refs.append(write(f"judgment-{index}.json", {
            "template_id": TEMPLATE_ID, "phrase": phrase, "note": note, "status": "draft",
            "observable_requirements": {"observables": observables, "context_inputs": contexts,
                "sweep_dimensions": [{"name": "participant_presence_at_exhibition", "unit": "categorical",
                    "description": "Compare physical occupancy and timing without choosing a legal cutoff."}],
                "landmarks": [], "recording_needs": observables,
                "limitations": ["Original source review is needed for permission and lawful use; no legal verdict is inferred from geometry."]},
        }))
    refs["judgment_observables"] = judgment_refs
    binding = {
        "cell_id": "C111125", "actor": ACTOR, "status": "draft",
        "established_contexts": ["intersection", "straight movement", "traffic light"],
        "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": name, "kind": type_, "range_or_domain": domain,
                                 "used_by_laws": [LAW]} for name, type_, domain in VARIABLES],
    }
    refs["bindings"] = write("bindings.json", binding)
    description = recording_description()
    common = {"target_law_id": LAW, "target_type": "boundary_probe",
              "recording_description": description,
              "unresolved_judgment_calls": [phrase for phrase, _ in PHRASES]}
    baseline = {"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Shared source-reviewed dual-aspect straight route without another user.",
                "variable_assignments": variable_assignments("dual_clear"),
                "recording_description": description,
                "unresolved_judgment_calls": [phrase for phrase, _ in PHRASES]}
    cases = [baseline]
    for row in plan["cases"]:
        suffix = row["case_id"].removeprefix(ASSIGNMENT + "__")
        pair = "vehicle_presence" if suffix in ("dual_clear", "dual_vehicle_present") else "pedestrian_exhibition_timing"
        differences = (["participant_kind", "participant_presence_at_exhibition"]
                       if pair == "vehicle_presence" else ["participant_presence_at_exhibition"])
        cases.append(dict(common, case_id=row["case_id"], rationale=row["purpose"],
                          variable_assignments=variable_assignments(suffix),
                          paired_probe_id=ASSIGNMENT + "__" + pair,
                          deliberate_differences=differences,
                          probe={"primary_variable": "participant_presence_at_exhibition",
                                 "comparison_or_standard": "Original source-backed participant presence at first dual-green exhibition; no legal cutoff",
                                 "target_value_or_branch": row["scenario_parameters"]["other_user_region_at_exhibition"]}))
    sweeps = [{"sweep_id": f"c111125-3a-{i}", "target_law_id": LAW,
               "judgment_refs": [{"phrase": phrase, "note": note}], "status": "incomplete",
               "rationale": "Original dual-aspect site and independent lawful-use sources must bound physical sweep feasibility.",
               "missing_inputs": ["Reviewed Native dual-aspect head and movement-restriction source",
                                  "Independent original lawful-use context and feasible participant timing range"]}
              for i, (phrase, note) in enumerate(PHRASES, 1)]
    refs["cases"] = write("cases.json", {"cell_id": "C111125", "actor": ACTOR,
                                           "status": "draft", "cases": cases,
                                           "sweep_specs": sweeps, "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": ASSIGNMENT,
                                  "source": {"path": f"inputs/{ASSIGNMENT}/assignment.json",
                                             "sha256": hashlib.sha256((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_bytes()).hexdigest()},
                                  "stages": refs, "status": "draft_source_review_pending"})
    print("authored", len(cases) - 1, "selected dual-green cases and", len(PHRASES), "judgment plans")


if __name__ == "__main__":
    build()
