"""Emit draft canonical stage proposals for the exact parking law and six cases.

This is a structural proposal only. Local review and stage-plan adoption remain
separate, and unresolved site/activity/exception facts are not asserted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parking_scene import ASSIGNMENT


ROOT = Path(__file__).resolve().parent
LAW = "LVMC-11-52-040-A"
ACTOR = "motor_vehicle_driver"
CELL = "C150041"
PHRASE = "parallel with the edge of the roadway"


def _write(directory, name, value):
    path = directory / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _recording():
    channels = [
        ("body_vertices_xy_m", "m", "Original Native bounding-box XY corners"),
        ("vehicle_forward_xy", "unit vector", "Original Native transform forward axis"),
        ("speed_m_s", "m/s", "Original Native velocity norm"),
        ("control", "structured record", "Original applied Native throttle, steer and brake"),
        ("camera_frame_map", "structured record", "Original four-camera/world frame join"),
    ]
    return {"channels": [{"name": name, "unit": unit, "sampling_rate_hz": 20,
                          "method": method, "time_window": "entire approach and stationary interval",
                          "reference_frame": "original CARLA world and frame/time",
                          "uncertainty": "Native motion and camera pixels require physical review"}
                         for name, unit, method in channels],
            "context_inputs": [
                {"name": "roadway_edge_and_polygon", "unit": "m in Native world XY",
                 "method": "SHA-256 retained reviewed roadway packet"},
                {"name": "lawful_one_way_direction", "unit": "unit vector",
                 "method": "SHA-256 retained reviewed direction packet"},
                {"name": "activity_and_chapter_exception_review", "unit": "source context",
                 "method": "Separate retained stand/park activity and Chapter source packets"},
            ],
            "limitations": ["Requested pose does not establish realized orientation or activity.",
                            "No numerical legal parallelism or edge-distance threshold is supplied.",
                            "Chapter exception and municipal applicability require source review."]}


def _assign(activity, orientation, heading):
    return {"roadway_context": {"kind": "world_setup", "value": "pending_reviewed_one_way_road",
                                "note": "Exact public roadway, edge and direction need retained source"},
            "activity_context": {"kind": "world_setup", "value": activity,
                                 "note": "Halt purpose and responsible person need retained source"},
            "orientation_request": {"kind": "controller", "value": orientation,
                                    "note": "Original body geometry measures realization"},
            "heading_request": {"kind": "controller", "value": heading,
                                "note": "Original transform measures realization"}}


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    if plan["assignment_id"] != ASSIGNMENT or plan["law_id"] != LAW:
        raise ValueError("exact law or assignment changed")
    quote = plan["law_text"]
    directory = ROOT / "proposals"
    directory.mkdir(exist_ok=True)
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
                                    "relevance_type": "direct roadway standing or parking orientation",
                                    "confidence": "low",
                                    "notes": "Site, activity and Chapter exception sources pending review."}],
                 "borderline_excluded": []}
    template = {"template_id": LAW + "@" + ACTOR, "law_id": LAW, "actor": ACTOR,
                "quote": quote,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "A person stands or parks a vehicle in a roadway, subject to another provision of this Chapter.",
                                             "numeric_conditions": []},
                              "obligation": {"description": "Vehicle is parallel with the roadway edge and headed in the direction of lawful traffic movement.",
                                             "type": "must", "numeric_conditions": []},
                              "exceptions": [{"trigger": "Otherwise provided in this Chapter",
                                              "effect": "Potential displacement or qualification of this clause; unresolved pending Chapter review",
                                              "replacement_obligation": None,
                                              "source_clause": "Except as otherwise provided in this Chapter"}],
                              "timing": {"description": "During the observed standing or parking interval.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": PHRASE,
                                                         "note": "No numeric angle tolerance is supplied; retain measured geometry for later judgment."}]},
                "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                                   for name, kind, domain in (
                                       ("roadway_context", "world_setup", "reviewed roadway, edge and lawful one-way direction"),
                                       ("activity_context", "world_setup", "reviewed stand or park purpose, person and Chapter context"),
                                       ("orientation_request", "controller", "parallel or angled engineering request"),
                                       ("heading_request", "controller", "lawful or reverse engineering request"))]}
    judgment = {"template_id": LAW + "@" + ACTOR, "phrase": PHRASE,
                "note": "No legal angular threshold is provided.", "status": "draft",
                "observable_requirements": {
                    "observables": [{"name": "parallel_deviation_deg", "unit": "deg",
                                     "description": "Absolute original body-axis/nearest-road-edge deviation"},
                                    {"name": "center_edge_distance_m", "unit": "m",
                                     "description": "Original body center distance to reviewed edge"}],
                    "context_inputs": [{"name": "reviewed_road_edge_xy_m", "unit": "m",
                                        "description": "Original retained roadway boundary geometry"},
                                       {"name": "reviewed_lawful_direction", "unit": "unit vector",
                                        "description": "Source-reviewed one-way direction"}],
                    "sweep_dimensions": [{"name": "orientation_request", "unit": "deg",
                                          "description": "Engineering angle request; no legal threshold"}],
                    "landmarks": [],
                    "recording_needs": [{"name": "original_body_and_heading_history", "unit": "20 Hz JSONL",
                                         "description": "Original full body/forward samples joined to camera and world frames"}],
                    "limitations": ["No reviewed site source or judgment range establishes a legal cutoff.",
                                    "Intent, activity and Chapter exceptions need separate source review."]}}
    bindings = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                "established_contexts": [],
                "law_refs": [{"template_id": LAW + "@" + ACTOR, "binding_kind": "direct"}],
                "context_refs": [{"template_id": LAW + "@" + ACTOR,
                                  "missing_guards": ["reviewed roadway and one-way direction",
                                                     "stand/park purpose and responsible person",
                                                     "applicable Chapter exceptions"]}],
                "fixed_parameters": [],
                "variable_parameters": [{"name": name, "kind": kind, "range_or_domain": domain,
                                         "used_by_laws": [LAW]}
                                        for name, kind, domain in (
                                            ("roadway_context", "world_setup", "reviewed one-way roadway packet"),
                                            ("activity_context", "world_setup", "stand or park source context"),
                                            ("orientation_request", "controller", "parallel or angled"),
                                            ("heading_request", "controller", "lawful or reverse"))]}
    cases = [{"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Neutral one-way parking setup definition; not a planned recording.",
              "variable_assignments": _assign("park", "parallel", "lawful"),
              "recording_description": _recording(),
              "unresolved_judgment_calls": [PHRASE]}]
    for planned in plan["cases"]:
        suffix = planned["case_id"].removeprefix(ASSIGNMENT + "__")
        activity = planned["activity_request"]
        variable = ("orientation_request" if planned["orientation_request"] == "angled"
                    else "heading_request" if planned["heading_request"] == "reverse"
                    else "orientation_request")
        cases.append({"case_id": planned["case_id"], "target_law_id": LAW,
                      "target_type": "boundary_probe",
                      "rationale": "Requested standing/parking pose; original geometry and legal context remain unverified.",
                      "variable_assignments": _assign(activity, planned["orientation_request"],
                                                      planned["heading_request"]),
                      "recording_description": _recording(),
                      "unresolved_judgment_calls": [PHRASE],
                      "paired_probe_id": activity + "_orientation_and_heading",
                      "deliberate_differences": [variable],
                      "probe": {"primary_variable": variable,
                                "comparison_or_standard": "original body axis and reviewed roadway edge/direction",
                                "target_value_or_branch": planned["orientation_request"] if variable == "orientation_request" else planned["heading_request"]}})
    proposal_cases = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                      "cases": cases,
                      "sweep_specs": [{"sweep_id": "parallel_orientation_source_pending",
                                       "target_law_id": LAW,
                                       "judgment_refs": [{"phrase": PHRASE,
                                                          "note": "No legal angular threshold is provided."}],
                                       "status": "incomplete", "mode": "one_dimensional",
                                       "missing_inputs": ["Reviewed physical one-way site and source-backed orientation feasibility",
                                                          "Approved judgment coverage range and spacing"],
                                       "axes": [], "landmarks": [],
                                       "rationale": "A source-backed sweep cannot be bounded from this frozen inventory.",
                                       "variable_assignments": _assign("park", "parallel", "lawful"),
                                       "recording_description": _recording()}]}
    stages = {"relevance_batch": _write(directory, "relevance_batch.json", relevance),
              "relevance": _write(directory, "relevance.json", relevance),
              "template": _write(directory, "template.json", template),
              "judgment_observables": [_write(directory, "judgment-1.json", judgment)],
              "bindings": _write(directory, "bindings.json", bindings),
              "cases": _write(directory, "cases.json", proposal_cases)}
    _write(directory, "semantic-index.json",
           {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
            "stages": stages, "status": "draft_source_binding_and_sweep_pending"})
    return stages


if __name__ == "__main__":
    build()
