"""Build four exact source-gated route semantic proposals."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN = json.loads((ROOT / "case-plan.json").read_text())
OUT = ROOT / "proposals"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(name: str, data: dict) -> dict:
    path = OUT / name
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return {"path": "proposals/" + name, "sha256": sha(path)}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    aid, law, cell, actor = (PLAN[key] for key in
                             ("assignment_id", "law_id", "cell_id", "actor"))
    quote = PLAN["law_text"]
    relevance = dump("relevance.json", {"cell_id": cell, "actor": actor,
        "status": "draft", "relevant_laws": [{"law_id": law, "quote": quote,
            "applies_to": [actor], "relevance_type": "source-gated controlled-access alternate-route duty",
            "confidence": "low", "notes": "Paved-road travel does not establish a controlled-access highway or an alternate route."}],
        "borderline_excluded": []})
    variables = {"route_choice": "controller", "alternate_declared": "world_setup",
                 "controlled_access": "world_setup", "ego_speed_mps": "controller",
                 "alternate_entry_lead_m": "world_setup"}
    refs = [{"name": name, "kind": kind,
             "range_or_domain": "selected route probe and reviewed original source"}
            for name, kind in variables.items()]
    template = dump("template.json", {"template_id": law + "@" + actor,
        "law_id": law, "actor": actor, "status": "draft", "quote": quote,
        "structure": {"law_id": law,
            "activation": {"condition": "A motor-vehicle driver travels so slowly as to impede traffic proceeding immediately behind on a controlled-access highway.",
                           "numeric_conditions": []},
            "obligation": {"description": "Use alternate routes whenever possible.",
                           "type": "must", "numeric_conditions": []},
            "exceptions": [], "timing": {"description": "Route choice during the journey when an alternate is possible.",
                                      "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": "so slow as to impede the forward movement of traffic proceeding immediately behind", "note": "Original follower movement and traffic context require review; no numeric legal cutoff."}, {"phrase": "whenever possible", "note": "Journey destination, restrictions and actual route are measured; legal possibility remains unresolved."}]},
        "parameter_refs": refs})
    judgment_refs = []
    for index, (phrase, note, name, dimension) in enumerate((
        ("so slow as to impede the forward movement of traffic proceeding immediately behind",
         "Original follower movement and traffic context require review; no numeric legal cutoff.",
         "follower_motion", "ego_speed_mps"),
        ("whenever possible",
         "Journey destination, restrictions and actual route are measured; legal possibility remains unresolved.",
         "journey_context", "alternate_entry_lead_m"))):
        judgment_refs.append(dump(f"judgment-{index}.json", {
            "template_id": law + "@" + actor, "phrase": phrase, "note": note,
            "status": "draft", "observable_requirements": {
                "context_inputs": [{"name": "highway", "unit": "source record",
                                    "description": "SHA-bound original map, journey and restriction source"}],
                "landmarks": [],
                "limitations": ["Original physical sources require independent review; no legal verdict is inferred."],
                "observables": [{"name": name, "unit": "m and m/s" if index == 0 else "source record",
                                 "description": "20 Hz original Native participant and route readback"}],
                "recording_needs": [{"name": name, "unit": "m and m/s" if index == 0 else "source record",
                                     "description": "Original saved channel and four-view camera review"}],
                "sweep_dimensions": [{"name": dimension, "unit": "m/s" if index == 0 else "m",
                                      "description": "Engineering sample only; no legal cutoff"}]}}))
    bindings = dump("bindings.json", {"cell_id": cell, "actor": actor,
        "status": "draft", "established_contexts": [
            "Paved-road travel with another vehicle; controlled access, immediately-behind relation, and alternate-route possibility require original review."],
        "law_refs": [{"template_id": law + "@" + actor, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [{"name": "maneuver", "kind": "world_setup",
            "value": "travel with route divergence", "source": "source-gated C179789 branch"}],
        "variable_parameters": [dict(item, used_by_laws=[law]) for item in refs]})
    channels = (
        ("native_frame", "frame", "original Native tick identity"),
        ("ego_motion", "m and m/s", "original ego transform and speed"),
        ("follower_motion", "m and m/s", "original follower transform, gap, and speed"),
        ("route_choice", "categorical", "original route station and terminal selection"),
        ("map_classification", "source record", "reviewed map and legal access source"),
        ("journey_context", "source record", "reviewed destination and route restriction"),
        ("four_camera_frames", "native pixels", "synchronized original four-view sources"),
        ("ego_speed_mps", "m/s", "original ego speed readback"),
        ("alternate_entry_lead_m", "m", "original station distance to alternate entry"),
    )
    description = {"channels": [{"name": name, "unit": unit, "method": method,
        "sampling_rate_hz": 20, "time_window": "full 900-frame, 45-second attempt",
        "reference_frame": "original CARLA world and frame identity",
        "uncertainty": "one retained 20 Hz sample"} for name, unit, method in channels],
        "context_inputs": [{"name": name, "unit": "source record",
            "method": "SHA-bound reviewed original site and restriction packet"} for name in
            ("highway", "controlled_access", "driver_and_vehicle", "alternate_restriction")],
        "limitations": ["Requested route is not observed route.",
            "Open alternate does not decide legal possibility or impediment."]}
    base_tags = {"alternate_selected", "alternate_not_selected",
                 "alternate_restricted", "ordinary_road_contrast"}
    base_rows = [row for row in PLAN["cases"]
                 if row["case_id"].rsplit("__", 1)[-1] in base_tags]
    if len(base_rows) != 4:
        raise ValueError("four original route probes missing")
    for row in base_rows:
        row["recording_description"] = description
    cases = [{"case_id": aid + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Unexecuted reference for linked route probes.",
        "variable_assignments": {name: {"kind": kind, "value": "unselected"}
                                 for name, kind in variables.items()},
        "unresolved_judgment_calls": [], "recording_description": description}]
    for row in base_rows:
        tag = row["case_id"].rsplit("__", 1)[-1]
        comparison = ("alternate_choice" if tag == "alternate_selected" else
                      "alternate_restriction" if tag == "alternate_restricted" else
                      "controlled_access" if tag == "ordinary_road_contrast" else
                      "alternate_choice")
        values = row["target"]
        cases.append({"case_id": row["case_id"], "target_law_id": law,
            "target_type": "boundary_probe",
            "rationale": "Request one route/availability/access contrast; original motion and legal possibility remain unverified.",
            "variable_assignments": {name: {"kind": kind, "value": values.get(name)}
                                     for name, kind in variables.items()},
            "unresolved_judgment_calls": ["so slow as to impede", "immediately behind", "whenever possible"],
            "paired_probe_id": comparison,
            "deliberate_differences": [{"alternate_choice": "route_choice",
                "alternate_restriction": "alternate_declared",
                "controlled_access": "controlled_access"}[comparison]],
            "probe": {"primary_variable": {"alternate_choice": "route_choice",
                "alternate_restriction": "alternate_declared",
                "controlled_access": "controlled_access"}[comparison],
                "comparison_or_standard": "source-reviewed route and original participant motion",
                "target_value_or_branch": tag},
            "recording_description": description})
    def assignments(route, alternate):
        return {"route_choice": {"kind": "controller", "value": route},
                "alternate_declared": {"kind": "world_setup", "value": True},
                "controlled_access": {"kind": "world_setup", "value": True},
                "ego_speed_mps": {"kind": "controller", "value": None,
                    "note": "Engineering speed request only; observed speed and legal impediment are unresolved."},
                "alternate_entry_lead_m": {"kind": "world_setup", "value": None,
                    "note": "Engineering route entry request only; legal possibility is unresolved."}}
    sweeps = [
        {"sweep_id": aid + "__impediment", "target_law_id": law,
         "judgment_refs": [{"phrase": "so slow as to impede the forward movement of traffic proceeding immediately behind",
             "note": "Original follower movement and traffic context require review; no numeric legal cutoff."}],
         "rationale": "Three requested ego speeds for physical sampling; no legal impediment threshold or realized speed is asserted.",
         "status": "complete", "mode": "one_dimensional", "landmarks": [],
         "variable_assignments": assignments("main", True),
         "recording_description": description,
         "axes": [{"variable": "ego_speed_mps", "observable": "ego_speed_mps",
             "unit": "m/s", "min": 4.0, "max": 6.0, "spacing": 1.0,
             "range_rationale": "Authored slow-speed controller requests for a 45-second route; not a legal cutoff or physical outcome.",
             "spacing_rationale": "Three distinguishable requests; realized spacing requires original trace review.",
             "feasibility_evidence": "source_gated_sweeps.py requires reviewed original speed feasibility before Native execution; CPU fake-source tests cover the three requests.",
             "measurement": {"method": "original 20 Hz ego speed readback",
                 "time_window": "entire original 45-second episode", "statistic": "mean"}}]},
        {"sweep_id": aid + "__route_possibility", "target_law_id": law,
         "judgment_refs": [{"phrase": "whenever possible",
             "note": "Journey destination, restrictions and actual route are measured; legal possibility remains unresolved."}],
         "rationale": "Three requested alternate-entry leads sample route opportunities; no legal possibility cutoff or physical outcome is asserted.",
         "status": "complete", "mode": "one_dimensional", "landmarks": [],
         "variable_assignments": assignments("alternate", True),
         "recording_description": description,
         "axes": [{"variable": "alternate_entry_lead_m", "observable": "alternate_entry_lead_m",
             "unit": "m", "min": 40.0, "max": 80.0, "spacing": 20.0,
             "range_rationale": "Authored alternate-entry lead requests for route geometry sampling; not a legal possibility cutoff.",
             "spacing_rationale": "Three distinct entry opportunities; original map support and realized spacing require review.",
             "feasibility_evidence": "source_gated_sweeps.py requires three reviewed original alternate route geometries before Native execution; CPU fake-source tests cover requests.",
             "measurement": {"method": "original Native route-station distance to selected alternate entry",
                 "time_window": "entire original 45-second episode", "statistic": "first"}}]},
    ]
    result = {"cell_id": cell, "actor": actor, "status": "draft",
              "cases": cases, "sweep_specs": sweeps}
    if "SCENARIO_PIPELINE_OUTPUT_ROOT" not in os.environ:
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before importing runtime")
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    from batch_pipeline.sweeps import expand_sweeps
    template_data = json.loads((OUT / "template.json").read_text())
    binding_data = json.loads((OUT / "bindings.json").read_text())
    expand_sweeps(result, [template_data], binding_data)
    case_ref = dump("cases.json", result)
    selected = [item for item in result["cases"] if item["target_type"] != "baseline"]
    if len(selected) != 10:
        raise ValueError("four route probes and six engineering stations required")
    sweep_rows = []
    for item in selected[4:]:
        values = {name: value["value"] for name, value in item["variable_assignments"].items()}
        sweep_rows.append({"case_id": item["case_id"], "kind": "delivery",
            "new_capture_selected": True, "target_law_id": law,
            "gap_ids": ["no-accepted-recording"], "branch": PLAN["selected_branch"],
            "target": dict(values, requested_duration_s=45,
                           engineering_request_not_legal_judgment=True),
            "recording_description": description,
            "physical_risk": {"status": "physical", "reason":
                "Original map opportunity, follower relation, controller readback and camera coverage require review."},
            "legal_judgment": "unresolved"})
    PLAN["cases"] = base_rows + sweep_rows
    PLAN["comparisons"] = [row for row in PLAN["comparisons"] if row["comparison_id"] not in
                            ("impediment_sweep", "route_possibility_sweep")]
    for sweep_id, comparison_id in (("impediment", "impediment_sweep"),
                                    ("route_possibility", "route_possibility_sweep")):
        members = [item["case_id"] for item in selected if item.get("sweep_id", "").endswith("__" + sweep_id)]
        PLAN["comparisons"].append({"comparison_id": comparison_id, "case_ids": members,
            "fixed_conditions": ["same reviewed journey, route context, actors, capture profile and non-axis controls"],
            "deliberate_differences": ["requested engineering " + sweep_id + " station only"]})
    for disposition in PLAN["requirement_dispositions"]:
        disposition["case_ids"] = [item["case_id"] for item in selected]
    (ROOT / "case-plan.json").write_text(json.dumps(PLAN, indent=2, sort_keys=True) + "\n")
    source = REPO / "inputs" / aid / "assignment.json"
    dump("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": aid,
        "source": {"path": source.relative_to(REPO).as_posix(), "sha256": sha(source)},
        "stages": {"relevance_batch": relevance, "relevance": relevance,
                   "template": template, "judgment_observables": judgment_refs,
                   "bindings": bindings, "cases": case_ref},
        "status": "draft_original_route_review_pending"})


if __name__ == "__main__":
    main()
