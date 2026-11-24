"""Build source-limited canonical semantic drafts for six exact crosswalk cases."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from case_construction import CASES
from crosswalk_measurements import ASSIGNMENT_ID

HERE = Path(__file__).resolve().parent
LAW = "LVMC-11-30-030"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
JUDGMENTS = (
    ("unmarked crosswalk at an intersection", "Actual road intersection, sidewalk lateral lines and curb or traveled-edge definition need original source review."),
    ("to permit a pedestrian to cross the roadway", "Lead stop purpose needs an independent original source; pedestrian movement alone cannot prove purpose."),
    ("approaching from the rear", "Original actor body history and road direction must establish the relative approach."),
    ("overtake and pass such stopped vehicle", "Original full body sequence must establish passage while the lead remains stopped; no numerical legal cutoff is supplied."),
)


def _write(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def recording_description() -> dict:
    def channel(name, method):
        return {"name": name, "unit": "structured record", "sampling_rate_hz": 20,
                "method": method, "time_window": "45 s original approach, lead stop and crossing",
                "reference_frame": "source-hashed Native world XY and elapsed time",
                "uncertainty": "20 Hz samples and physical visibility require original review"}
    return {"channels": [
        channel("ego_body_history", "Original ego eight-vertex body, center and velocity every Native tick"),
        channel("lead_body_history", "Original lead eight-vertex body, center and velocity every Native tick"),
        channel("original_actor_body_sequence", "Original joined ego/lead/pedestrian actor identities, bodies and speeds"),
        channel("pedestrian_history", "Original pedestrian center and actor identity every Native tick"),
        channel("four_camera_frame_map", "Four original RGB camera frames joined to each Native tick"),
        channel("complete_native_source_and_pixels", "Full original actor trace and decoded four-view pixels at every Native tick")],
        "context_inputs": [
            {"name": "intersection_crosswalk_geometry", "unit": "source packet",
             "method": "SHA-bound OpenDRIVE, intersection, opposite sidewalks, curb/edge and marking source where applicable"},
            {"name": "lead_stop_purpose", "unit": "original observer statement",
             "method": "Independently cited and SHA-bound source distinct from pedestrian motion"},
            {"name": "original_crosswalk_and_purpose", "unit": "source packet",
             "method": "Cited original road intersection, crossing geometry and independent stop-purpose source"}],
        "limitations": ["Sampled motion and pixels cannot alone establish legal crosswalk status or driver purpose.",
                        "Physical passage and visibility require original Native review; legal judgment remains unresolved."]}


def build() -> dict:
    assignment = json.loads((HERE.parents[1] / "inputs" / ASSIGNMENT_ID / "assignment.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    quote = assignment["law"]["text"]
    if plan.get("law_text") != quote or len(plan.get("cases", [])) != len(CASES):
        raise ValueError("exact source law and six planned cases required")
    proposals = HERE / "proposals"
    relevance = {"cell_id": "C229023", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
                                    "relevance_type": "stopped-crosswalk rear overtaking prohibition",
                                    "confidence": "low", "notes": "Broad road cell needs original road-intersection, crosswalk and stopped-purpose review."}],
                 "borderline_excluded": []}
    for name in ("relevance_batch", "relevance"):
        _write(proposals / (name + ".json"), relevance)
    judgments = [{"phrase": phrase, "note": note} for phrase, note in JUDGMENTS]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "quote": quote,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "A vehicle is stopped at a marked crosswalk or an unmarked crosswalk at an intersection to permit pedestrian crossing; another driver approaches from the rear.",
                                             "numeric_conditions": []},
                              "obligation": {"description": "The rear-approaching driver shall not overtake and pass the stopped vehicle.",
                                             "type": "must_not", "numeric_conditions": []},
                              "exceptions": [],
                              "timing": {"description": "Observe lead stopped state, rear approach and complete passage in original frame order.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": judgments},
                "parameter_refs": [
                    {"name": "crosswalk_kind", "kind": "world_setup", "range_or_domain": "source-marked or source-defined unmarked intersection crosswalk"},
                    {"name": "ego_behavior", "kind": "controller", "range_or_domain": "wait or pass request, measured afterward"},
                    {"name": "lead_stop_purpose", "kind": "world_setup", "range_or_domain": "independently sourced pedestrian-permitting or other purpose"}]}
    _write(proposals / "template.json", template)
    judgment_paths = []
    for index, (phrase, note) in enumerate(JUDGMENTS, 1):
        name = f"judgment-{index}.json"
        requirements = {"observables": [
            {"name": "original_actor_body_sequence", "unit": "structured record",
             "description": "Original 20 Hz identities, centers, body vertices and speeds for both vehicles and pedestrian."}],
            "context_inputs": [
                {"name": "original_crosswalk_and_purpose", "unit": "source packet",
                 "description": "Independent map, crossing geometry and stopped-purpose citations."}],
            "sweep_dimensions": [{"name": "crosswalk_kind_and_ego_request", "unit": "categorical",
                                  "description": "Exact marked/unmarked and wait/pass alternatives held fixed by declared comparison."}],
            "landmarks": [],
            "recording_needs": [{"name": "complete_native_source_and_pixels", "unit": "structured record",
                                 "description": "Full 900-tick actor trace, frame map and four decoded original views."}],
            "limitations": [note, "No legal conclusion follows from a controller request or synthetic CPU fixture."]}
        _write(proposals / name, {"template_id": TEMPLATE, "phrase": phrase, "note": note,
                                  "status": "draft", "observable_requirements": requirements})
        judgment_paths.append(name)
    variables = [{"name": name, "kind": kind, "range_or_domain": domain, "used_by_laws": [LAW]}
                 for name, kind, domain in (
                     ("crosswalk_kind", "world_setup", "marked or unmarked, source-backed"),
                     ("ego_behavior", "controller", "wait or pass request; actual motion measured"),
                     ("lead_stop_purpose", "world_setup", "independent observer source claim"))]
    _write(proposals / "bindings.json", {"cell_id": "C229023", "actor": ACTOR, "status": "draft",
                                      "established_contexts": ["assigned broad road cell; actual intersection and crossing source review pending"],
                                      "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
                                      "context_refs": [], "fixed_parameters": [], "variable_parameters": variables})
    recording = recording_description()
    baseline_row = plan["cases"][0]
    cases = [{"case_id": ASSIGNMENT_ID + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Shared semantic reference; no additional selected recording.",
              "variable_assignments": {
                  "crosswalk_kind": {"kind": "world_setup", "value": baseline_row["crosswalk_kind"]},
                  "ego_behavior": {"kind": "controller", "value": baseline_row["ego_maneuver_request"]},
                  "lead_stop_purpose": {"kind": "world_setup", "value": baseline_row["stopped_vehicle_purpose_claim"]}},
              "recording_description": recording, "unresolved_judgment_calls": []}]
    for row in plan["cases"]:
        suffix = row["case_id"].removeprefix(ASSIGNMENT_ID + "__")
        crossing, behavior, purpose = CASES[suffix]
        if (row["crosswalk_kind"], row["ego_maneuver_request"], row["stopped_vehicle_purpose_claim"]) != (crossing, behavior, purpose):
            raise ValueError("exact case alternatives changed")
        assignments = {"crosswalk_kind": {"kind": "world_setup", "value": crossing},
                       "ego_behavior": {"kind": "controller", "value": behavior},
                       "lead_stop_purpose": {"kind": "world_setup", "value": purpose}}
        differences = [name for name, value in assignments.items()
                       if value["value"] != cases[0]["variable_assignments"][name]["value"]]
        cases.append({"case_id": row["case_id"], "target_law_id": LAW, "target_type": "boundary_probe",
                      "rationale": "Source-bound exact alternative and controlled comparison; no legal outcome is asserted.",
                      "variable_assignments": assignments, "recording_description": recording,
                      "unresolved_judgment_calls": [phrase for phrase, _ in JUDGMENTS],
                      "paired_probe_id": "crosswalk_stop_and_pass_contrasts",
                      "deliberate_differences": differences,
                      "probe": {"primary_variable": differences[0] if differences else "ego_behavior",
                                "comparison_or_standard": "observed original actor sequence",
                                "target_value_or_branch": suffix}})
    sweeps = [{"sweep_id": f"crosswalk-judgment-{index}", "target_law_id": LAW,
               "judgment_refs": [{"phrase": phrase, "note": note}], "status": "incomplete",
               "rationale": "Source and original physical review remain necessary; no numeric legal cutoff inferred.",
               "missing_inputs": ["reviewed original intersection/crosswalk/purpose source and Native acquisition"]}
              for index, (phrase, note) in enumerate(JUDGMENTS, 1)]
    _write(proposals / "cases.json", {"cell_id": "C229023", "actor": ACTOR, "status": "draft",
                                   "sweeps_expanded": True, "sweep_specs": sweeps, "cases": cases})
    paths = {"relevance_batch": "relevance_batch.json", "relevance": "relevance.json",
             "template": "template.json", "judgment_observables": judgment_paths,
             "bindings": "bindings.json", "cases": "cases.json"}
    stages = {key: ([{"path": "proposals/" + name,
                      "sha256": hashlib.sha256((proposals / name).read_bytes()).hexdigest()} for name in names]
                    if isinstance(names, list) else {"path": "proposals/" + names,
                                                      "sha256": hashlib.sha256((proposals / names).read_bytes()).hexdigest()})
              for key, names in paths.items()}
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT_ID,
             "stages": stages, "status": "draft_original_source_and_physical_review_pending"}
    _write(proposals / "semantic-index.json", index)
    return index


if __name__ == "__main__":
    build()
    print("built four source-limited judgment proposals and six exact cases")
