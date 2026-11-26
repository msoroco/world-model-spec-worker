"""Build the exact draft semantic stage chain for NRS 484B.270(2)(b)."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / "proposals"
LAW = "NRS-484B-270-2b"
ACTOR = "motor_vehicle_driver"
TEMPLATE_ID = LAW + "@" + ACTOR


def put(name, value):
    PROPOSALS.mkdir(exist_ok=True)
    target = PROPOSALS / name
    target.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    return {"path": str(target.relative_to(HERE)),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def assignment(kind, value, unit):
    return {"kind": kind, "value": value, "unit": unit}


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    quote = plan["law_text"]
    recording = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())[
        "recording_description"]
    relevance = {"cell_id": "C272352", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote,
                                    "applies_to": [ACTOR], "confidence": "high"}],
                 "borderline_excluded": []}
    relevance_ref = put("relevance.json", relevance)
    parameters = [
        {"name": "control_kind", "kind": "world_setup",
         "range_or_domain": "bicycle, electric bicycle or electric scooter",
         "unit": "source request"},
        {"name": "target_clearance_m", "kind": "controller",
         "range_or_domain": "nonnegative source-requested lateral body gap in metres",
         "unit": "m"},
        {"name": "return_request", "kind": "controller",
         "range_or_domain": "early or after_clear", "unit": "source request"},
        {"name": "route_request", "kind": "controller",
         "range_or_domain": "within_right_half, centerline or no_passing_zone",
         "unit": "source request"},
    ]
    judgments = [
        ("due-care", "due care", "Original motion and traffic do not alone resolve due care.",
         ["body_envelopes", "opposing_traffic", "camera_identity"]),
        ("safe-distance", "safe distance", "The three-foot floor does not alone resolve safe distance.",
         ["body_envelopes", "passing_clearance", "camera_identity"]),
        ("safely-clear", "safely clear", "Original body ordering is evidence, not a legal safely-clear verdict.",
         ["body_envelopes", "return_order", "camera_identity"]),
        ("if-safe", "if it is safe", "Opposing traffic and incorporated exceptions need independent review.",
         ["lane_controls", "opposing_traffic", "camera_identity"]),
    ]
    template = {"template_id": TEMPLATE_ID, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": quote,
                "structure": {"law_id": LAW,
                    "activation": {"condition": "Motor vehicle overtakes or passes a qualifying bicycle, electric bicycle or electric scooter proceeding in the same direction.",
                                   "numeric_conditions": []},
                    "obligation": {"description": "On one same-direction lane, exercise due care, pass left at a safe distance not less than three feet, and stay left until safely clear.",
                                   "type": "must", "numeric_conditions": [{
                                       "variable": "measured_body_clearance_m", "operator": ">=",
                                       "value": 0.9144, "unit": "m",
                                       "source_clause": "not less than 3 feet between any portion of the vehicle and the bicycle, electric bicycle or electric scooter"}]},
                    "exceptions": [{"source_clause": "Except as otherwise provided in NRS 484B.213 and 484B.217",
                                    "disposition": "incorporated sources and applicability require original review"},
                                   {"source_clause": "if it is safe",
                                    "disposition": "centerline/no-passing authorization safety requires original review"}],
                    "timing": {"description": "During original longitudinal passing overlap and before return right.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                              for _, phrase, note, _ in judgments]},
                "parameter_refs": parameters}
    template_ref = put("template.json", template)
    judgment_refs = []
    by_name = {item["name"]: item for item in recording["channels"]}
    for slug, phrase, note, channels in judgments:
        requirement = {"observables": [{"name": channel,
                                          "unit": by_name[channel]["unit"],
                                          "description": "Original source-joined " + channel}
                                         for channel in channels],
                       "context_inputs": [{"name": "reviewed_native_site_packet",
                                           "unit": "source record",
                                           "description": "Sealed original map, actors, controls and exceptions"}],
                       "sweep_dimensions": [], "landmarks": [],
                       "recording_needs": [{"name": channel,
                                             "unit": by_name[channel]["unit"],
                                             "description": "Original 20 Hz " + channel}
                                            for channel in channels],
                       "limitations": ["Qualitative legal judgments remain unresolved by synthetic fixtures."]}
        judgment_refs.append(put("judgment-" + slug + ".json",
                                 {"template_id": TEMPLATE_ID, "phrase": phrase,
                                  "note": note, "status": "draft",
                                  "observable_requirements": requirement}))
    binding_ref = put("bindings.json", {"cell_id": "C272352", "actor": ACTOR,
        "status": "draft", "law_refs": [{"template_id": TEMPLATE_ID,
                                          "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "same_direction_lane_count_requested",
                              "kind": "world_setup", "value": 1,
                              "unit": "source request"}],
        "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in parameters]})
    baseline_values = {"control_kind": "bicycle", "target_clearance_m": 1.2,
                       "return_request": "after_clear", "route_request": "within_right_half"}
    def values(mapping):
        return {name: assignment(parameter["kind"], mapping[name], parameter["unit"])
                for parameter in parameters for name in (parameter["name"],)}
    baseline = {"case_id": plan["assignment_id"] + "__shared_baseline",
                "target_law_id": None, "target_type": "baseline", "status": "draft",
                "rationale": "Shared one-lane qualifying-rider source request; no accepted recording.",
                "variable_assignments": values(baseline_values),
                "unresolved_judgment_calls": [phrase for _, phrase, _, _ in judgments],
                "recording_description": recording}
    cases = [baseline]
    for entry in manifest["cases"]:
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        source = config["case"]
        mapping = {name: source[name] for name in baseline_values}
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        boundary = suffix in ("bike_clearance_below", "bike_clearance_at",
                              "bike_clearance_above")
        probe = {"primary_variable": "target_clearance_m" if boundary else
                 ("control_kind" if suffix.startswith("electric_") else
                  "route_request" if suffix.endswith("authorized") else
                  "return_request"),
                 "comparison_or_standard": "Original body geometry and source records; no qualitative legal verdict.",
                 "target_value_or_branch": suffix}
        if boundary:
            probe.update(threshold_ref="obligation.numeric_conditions[0]",
                         operator=">=", unit="m",
                         test_value=mapping["target_clearance_m"])
        cases.append({"case_id": entry["case_id"], "target_law_id": LAW,
            "target_type": "boundary_probe", "status": "draft",
            "rationale": "Controlled exact passing source request; physical and legal judgments unresolved.",
            "paired_probe_id": "three_foot_boundary" if boundary else suffix,
            "deliberate_differences": [name for name in baseline_values
                                       if mapping[name] != baseline_values[name]],
            "variable_assignments": values(mapping),
            "unresolved_judgment_calls": [phrase for _, phrase, _, _ in judgments],
            "recording_description": recording, "probe": probe,
            **({"epsilon_used": True} if boundary else {})})
    sweep = {"sweep_id": "qualitative-passing-review", "target_law_id": LAW,
             "judgment_refs": [{"phrase": phrase, "note": note}
                               for _, phrase, note, _ in judgments],
             "status": "incomplete", "rationale": "Original feasibility and source-reviewed ranges are required before freezing qualitative judgment sweeps.",
             "missing_inputs": ["Original Native geometry and feasible sweep ranges for due care, safe distance, safely clear and route safety"]}
    cases_ref = put("cases.json", {"cell_id": "C272352", "actor": ACTOR,
                                   "status": "draft", "sweep_specs": [sweep],
                                   "sweeps_expanded": True, "cases": cases})
    put("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": plan["assignment_id"], "status": "source_gated_draft",
        "stages": {"relevance_batch": relevance_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": judgment_refs,
                   "bindings": binding_ref, "cases": cases_ref}})
    return len(cases) - 1


if __name__ == "__main__":
    print("semantic exact cases:", build())
