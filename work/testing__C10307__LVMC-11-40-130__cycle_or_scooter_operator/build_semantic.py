"""Build source-faithful draft semantic stages without adopting them locally."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = json.loads((ROOT.parents[1] / "inputs" / ROOT.name / "assignment.json").read_text())
LAW = ASSIGNMENT["law"]
LAW_ID = ASSIGNMENT["law_id"]
ACTOR = ASSIGNMENT["actor"]
TEMPLATE_ID = f"{LAW_ID}@{ACTOR}"
PHRASE = "reasonable and prudent under the conditions then existing"
NOTE = "The text supplies no numeric prudence threshold; actual conditions require source review."


def write(name: str, value: dict) -> dict:
    path = ROOT / "proposals" / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": f"proposals/{name}",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def item(name: str, unit: str, description: str) -> dict:
    return {"name": name, "unit": unit, "description": description}


def build() -> dict:
    relevance = {
        "cell_id": ASSIGNMENT["cell_id"], "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW_ID, "quote": LAW["text"],
                           "applies_to": [ACTOR], "relevance_type": "direct bicycle speed rule",
                           "confidence": "high",
                           "notes": "The assigned alley travel branch concerns a bicycle; human power and municipal jurisdiction remain source facts."}],
        "borderline_excluded": []}
    relevance_ref = write("relevance.json", relevance)
    batch_ref = write("relevance_batch.json", relevance)
    template = {
        "template_id": TEMPLATE_ID, "law_id": LAW_ID, "actor": ACTOR,
        "quote": LAW["text"],
        "structure": {
            "law_id": LAW_ID,
            "activation": {"condition": "A person operates a bicycle.", "numeric_conditions": []},
            "obligation": {"description": "Do not operate the bicycle at a speed greater than is reasonable and prudent under the conditions then existing.",
                           "type": "must_not", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Measure bicycle speed and the conditions during the same original episode.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": PHRASE, "note": NOTE}]},
        "parameter_refs": [
            {"name": "ego_speed", "kind": "subject_behavior", "range_or_domain": "observed bicycle speed in m/s, trace only"},
            {"name": "commanded_approach_speed", "kind": "controller", "range_or_domain": "physical bicycle speed target in m/s, no legal threshold"},
            {"name": "visibility_condition", "kind": "world_setup", "range_or_domain": "original clear or reduced visibility"},
            {"name": "surface_condition", "kind": "world_setup", "range_or_domain": "original dry or wet surface"},
            {"name": "pedestrian_near_rack", "kind": "world_setup", "range_or_domain": "original absence or presence near rack"}]}
    template_ref = write("template.json", template)
    observations = [
        item("actual_bicycle_speed", "m/s", "Original per-frame bicycle body speed from Native velocity and frame map."),
        item("contemporaneous_conditions", "structured", "Original weather, surface, visibility and pedestrian history contemporaneous with speed.")]
    judgment = {
        "template_id": TEMPLATE_ID, "phrase": PHRASE, "note": NOTE, "status": "draft",
        "observable_requirements": {
            "observables": observations,
            "context_inputs": [
                item("bicycle_classification", "structured", "Source classification of the actual human-powered bicycle; moped exclusion remains explicit."),
                item("jurisdiction", "structured", "Source for the actual map being within City of Las Vegas.")],
            "sweep_dimensions": [
                item("commanded_approach_speed", "m/s", "Frozen physical bicycle controller setpoint; actual body velocity remains separately measured."),
                item("actual_bicycle_speed", "m/s", "Measured bicycle speed across physical controller targets, without a prudence cutoff."),
                item("visibility_condition", "categorical", "Clear and reduced original visibility histories."),
                item("surface_condition", "categorical", "Dry and wet original surface histories."),
                item("pedestrian_near_rack", "categorical", "Absent and present original pedestrian histories near the rack.")],
            "landmarks": [], "recording_needs": observations,
            "limitations": ["Speed and conditions do not determine legal prudence by themselves.",
                            "Physical bicycle classification, municipal jurisdiction, rack pixels and visibility require independent source review."]}}
    judgment_ref = write("judgment-1.json", judgment)
    binding = {
        "cell_id": ASSIGNMENT["cell_id"], "actor": ACTOR, "status": "draft",
        "established_contexts": ["alley", "bicycle rack", "travel"],
        "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}], "context_refs": [],
        "fixed_parameters": [
            {"name": "alley_route", "value": "source-bound C10307 alley travel route", "rationale": "Assigned cell geometry."},
            {"name": "bicycle_rack_geometry", "value": "source-bound rack on alley route", "rationale": "Assigned cell control."}],
        "variable_parameters": [
            {"name": p["name"], "kind": p["kind"], "range_or_domain": p["range_or_domain"],
             "used_by_laws": [LAW_ID]} for p in template["parameter_refs"]]}
    binding_ref = write("bindings.json", binding)
    original = json.loads((ROOT / "proposals" / "cases.json").read_text())
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    recording = json.loads((ROOT / "construction.json").read_text())["recording_description"]
    def assignments(target: float, visibility: str, surface: str, pedestrian: bool) -> dict:
        values = {"ego_speed": ("subject_behavior", None),
                  "commanded_approach_speed": ("controller", target),
                  "visibility_condition": ("world_setup", visibility),
                  "surface_condition": ("world_setup", surface),
                  "pedestrian_near_rack": ("world_setup", pedestrian)}
        return {name: {"kind": kind, "value": value} for name, (kind, value) in values.items()}
    baseline = {"case_id": f"{ASSIGNMENT['assignment_id']}__semantic_baseline",
                "target_law_id": None, "target_type": "baseline", "rationale": "Shared physical context only; no legal label.",
                "variable_assignments": assignments(3.0, "clear", "dry", False),
                "recording_description": recording, "unresolved_judgment_calls": []}
    groups = {"reference": (3.0, "clear", "dry", False, "speed_under_clear_conditions", "commanded_approach_speed"),
              "faster": (5.0, "clear", "dry", False, "speed_under_clear_conditions", "commanded_approach_speed"),
              "reduced_visibility": (3.0, "reduced", "dry", False, "visibility_at_reference_speed", "visibility_condition"),
              "pedestrian_near_rack": (3.0, "clear", "dry", True, "pedestrian_at_reference_speed", "pedestrian_near_rack"),
              "wet_surface": (3.0, "clear", "wet", False, "surface_at_reference_speed", "surface_condition")}
    selected = []
    sweep_id = "c10307-speed-under-clear-conditions"
    speed_axis = {"variable": "commanded_approach_speed", "observable": "commanded_approach_speed",
                  "unit": "m/s", "min": 3.0, "max": 5.0, "spacing": 2.0,
                  "range_rationale": "The two frozen clear/dry source cases command 3 and 5 m/s; these endpoints sample physical speed without setting a legal threshold.",
                  "spacing_rationale": "A single 2 m/s interval retains both authored case targets and avoids inventing an unbuilt case.",
                  "feasibility_evidence": "The pinned offline and compatibility proofs execute the 3 and 5 m/s controller profiles; physical realization remains unverified until a Native source run.",
                  "measurement": {"method": "Read the commanded target from the frozen case controller and retain Native body velocity in the raw trace.",
                                  "time_window": "The original 0 to 30 s capture window.", "statistic": "first"}}
    sweep_spec = {"sweep_id": sweep_id, "target_law_id": LAW_ID,
                  "judgment_refs": [{"phrase": PHRASE, "note": NOTE}], "status": "complete",
                  "rationale": "Finite physical speed sampling at fixed clear, dry, pedestrian-absent conditions; legal prudence remains unresolved.",
                  "mode": "one_dimensional", "axes": [speed_axis], "landmarks": [],
                  "recording_description": recording}
    sweep_spec["spec_version"] = hashlib.sha256(json.dumps(sweep_spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    sweep_spec["planned_case_count"] = 2
    sweep_spec["selection_order"] = [entry["case_id"] for entry in manifest["cases"] if entry["case_id"].endswith(("__reference", "__faster"))]
    for source, entry in zip(original["cases"], manifest["cases"]):
        suffix = entry["case_id"].rsplit("__", 1)[1]
        target, visibility, surface, pedestrian, pair, variable = groups[suffix]
        selected_case = {"case_id": entry["case_id"], "target_law_id": LAW_ID,
                         "target_type": "judgment_sweep", "rationale": source["rationale"],
                         "paired_probe_id": pair, "deliberate_differences": [variable],
                         "probe": {"primary_variable": variable,
                                   "comparison_or_standard": "physical coverage; legal judgment unresolved",
                                   "target_value_or_branch": {"target_speed_mps": target, "visibility": visibility,
                                                              "surface": surface, "pedestrian": pedestrian}},
                         "variable_assignments": assignments(target, visibility, surface, pedestrian),
                         "recording_description": recording,
                         "unresolved_judgment_calls": [PHRASE]}
        if suffix in ("reference", "faster"):
            selected_case.update({"sweep_id": sweep_id, "sweep_spec_version": sweep_spec["spec_version"],
                                  "sweep_point": {"commanded_approach_speed": target},
                                  "selection_rank": 0 if suffix == "reference" else 1,
                                  "judgment_refs": sweep_spec["judgment_refs"],
                                  "sweep_measurements": [{"variable": speed_axis["variable"],
                                                          "observable": speed_axis["observable"],
                                                          "unit": speed_axis["unit"],
                                                          "measurement": speed_axis["measurement"]}]})
        selected.append(selected_case)
    cases_stage = {"cell_id": ASSIGNMENT["cell_id"], "actor": ACTOR, "status": "draft",
                   "cases": [baseline, *selected],
                   "sweep_specs": [sweep_spec],
                   "sweeps_expanded": True}
    cases_ref = write("cases-stage.json", cases_stage)
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT["assignment_id"],
             "status": "partial", "stages": {"relevance_batch": batch_ref, "relevance": relevance_ref,
                                          "template": template_ref, "judgment_observables": [judgment_ref],
                                          "bindings": binding_ref, "cases": cases_ref},
             "remaining_stages": []}
    write("semantic-index.json", index)
    return index


if __name__ == "__main__":
    build()
