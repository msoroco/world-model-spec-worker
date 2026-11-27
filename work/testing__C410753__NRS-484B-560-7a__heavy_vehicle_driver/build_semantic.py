"""Author canonical NRS 484B.560(7)(a)/(8) stages for the exact rail cell."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "proposals"
AID = HERE.name
LAW = "NRS-484B-560-7a"
CELL = "C410753"
ACTOR = "heavy_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def parameter(name, kind, domain):
    return {"name": name, "kind": kind, "range_or_domain": domain}


def build():
    original = json.loads((HERE.parents[1] / "inputs" / AID / "assignment.json").read_text())
    quote = original["law"]["text"]
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
          "relevance_type": "heavy vehicle crossing a railroad track at grade",
          "confidence": "medium", "notes": "Opposite-side space, undercarriage clearance, stopping cause and trailer extent require original source review."}],
        "borderline_excluded": []}
    batch_ref = write("relevance_batch.json", relevance)
    relevance_ref = write("relevance.json", relevance)
    judgments = [
        {"phrase": "due to insufficient", "note": "Causality requires original obstruction, contact, control and traffic-conflict review; no gap cutoff is invented."},
        {"phrase": "nearest rail", "note": "Actual multi-track rail identity and trailing-end projection are retained; geometric interpretation requires review."}]
    refs = [parameter("construction_axis", "world_setup", "opposite_space, undercarriage or completion"),
            parameter("physical_mode", "controller", "halt, clear, below, at or above"),
            parameter("target_trailing_end_ft", "controller", "14.9, 15.0 or 15.1 ft engineering probes"),
            parameter("rail_geometry", "world_setup", "source-reviewed at-grade railroad tracks"),
            parameter("vehicle_class", "world_setup", "source-reviewed heavy vehicle and coupled configuration")]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "quote": quote,
        "structure": {"law_id": LAW,
            "activation": {"condition": "A driver of a vehicle crosses at grade a railroad track or tracks.",
                           "numeric_conditions": []},
            "obligation": {"description": "Do not fail to completely cross the track or tracks without stopping due to insufficient opposite-side space or undercarriage clearance.",
                           "type": "must_not", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Completely cross means the actual trailing end is 15 feet or more past the nearest rail of the track or tracks; observe any intervening stop and its physical cause.",
                       "numeric_conditions": [{"variable": "target_trailing_end_ft", "operator": ">=", "value": 15, "unit": "ft"}]},
            "judgment_calls_needed": judgments},
        "parameter_refs": refs}
    template_ref = write("template.json", template)
    observed = []
    for index, judgment in enumerate(judgments, 1):
        obs = {"template_id": TEMPLATE, "phrase": judgment["phrase"],
            "note": judgment["note"], "status": "draft", "observable_requirements": {
                "observables": [{"name": "trailing_end_distance_ft", "unit": "structured",
                    "description": "Original heavy and coupled-unit trailing body past source-reviewed rail geometry."},
                    {"name": "undercarriage_contact", "unit": "structured",
                    "description": "Original vehicle/road-profile contact and source of any observed halt."}],
                "context_inputs": [{"name": "reviewed_railway_site", "unit": "source",
                    "description": "Original railroad track, opposite-side obstruction, road profile and heavy-vehicle source."}],
                "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": "four_view_frame_join", "unit": "structured",
                    "description": "Original synchronized rails, full vehicle, downstream obstacle and ground contact views."}],
                "limitations": ["No causal or legal meaning is inferred from a CPU fixture or requested engineering target."]}}
        observed.append(write(f"judgment-{index}.json", obs))
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": ["Frozen paved-road railroad crossing and heavy-vehicle driver; actual reviewed site pending."],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "reviewed_railway_site", "value": "source_packet_pending",
                              "rationale": "Hold actual rail geometry, heavy/coupled-unit configuration, camera and duration across linked contrasts."}],
        "variable_parameters": [dict(ref, used_by_laws=[LAW]) for ref in refs]}
    binding_ref = write("bindings.json", binding)
    description = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())["recording_description"]
    cases = [{"case_id": AID + "__baseline", "paired_probe_id": "baseline",
        "rationale": "Shared source-reviewed grade-crossing and heavy-vehicle reference; baseline is not dispatched.",
        "recording_description": description, "target_law_id": LAW,
        "target_type": "baseline",
        "unresolved_judgment_calls": [j["phrase"] for j in judgments],
        "variable_assignments": {
            "construction_axis": {"kind": "world_setup", "value": "opposite_space"},
            "physical_mode": {"kind": "controller", "value": "clear"},
            "target_trailing_end_ft": {"kind": "controller", "value": 15.0},
            "rail_geometry": {"kind": "world_setup", "value": "source-reviewed grade crossing"},
            "vehicle_class": {"kind": "world_setup", "value": "source-reviewed heavy vehicle"}},
        "deliberate_differences": [ref["name"] for ref in refs],
        "probe": {"primary_variable": "physical_mode",
                  "comparison_or_standard": "original heavy-vehicle railway passage",
                  "target_value_or_branch": "clear"}}]
    for row in plan["cases"]:
        case_id = row["case_id"]
        name = case_id.removeprefix(AID + "__")
        if name.startswith("space_"):
            axis, mode = "opposite_space", "halt" if "halt" in name else "clear"
        elif name.startswith("clearance_"):
            axis, mode = "undercarriage", "halt" if "grounded" in name else "clear"
        else:
            axis, mode = "completion", "below" if "14_9" in name else "at" if "15_0" in name else "above"
        target = {"below": 14.9, "at": 15., "above": 15.1}.get(mode, 15.)
        values = {"construction_axis": {"kind": "world_setup", "value": axis},
                  "physical_mode": {"kind": "controller", "value": "probe" if axis == "completion" else mode},
                  "target_trailing_end_ft": {"kind": "controller", "value": target},
                  "rail_geometry": {"kind": "world_setup", "value": "source-reviewed grade crossing"},
                  "vehicle_class": {"kind": "world_setup", "value": "source-reviewed heavy vehicle"}}
        numeric = axis == "completion"
        probe = {"primary_variable": "target_trailing_end_ft" if numeric else "physical_mode",
                 "comparison_or_standard": "actual trailing body projection past nearest source rail" if numeric else "original physical halt and specified-cause source",
                 "target_value_or_branch": target if numeric else mode}
        if numeric:
            probe.update({"threshold_ref": "timing.numeric_conditions[0]", "operator": ">=",
                          "unit": "ft", "test_value": target})
        entry = {"case_id": case_id,
                 "paired_probe_id": "trailing_end_15ft_boundary" if numeric else axis,
                 "rationale": row["rationale"], "recording_description": description,
                 "target_law_id": LAW, "target_type": "boundary_probe",
                 "unresolved_judgment_calls": [j["phrase"] for j in judgments],
                 "variable_assignments": values,
                 "deliberate_differences": ["target_trailing_end_ft"] if numeric else ["physical_mode"],
                 "probe": probe}
        if numeric:
            entry["epsilon_used"] = {"value": .1, "unit": "ft",
                "rationale": "One-tenth-foot diagnostic increment around the statutory 15-foot distance; actual rail/body measurement uncertainty retained."}
        cases.append(entry)
    sweeps = [{"sweep_id": "legal_phrase_" + str(i), "target_law_id": LAW,
               "judgment_refs": [j], "status": "incomplete",
               "rationale": "No exact-law accepted judgment-range bounds or physical source outcome are supplied.",
               "missing_inputs": ["Original cause or rail-identity evidence suitable for a reviewed phrase-specific physical sweep."]}
              for i, j in enumerate(judgments, 1)]
    cases_ref = write("cases.json", {"cell_id": CELL, "actor": ACTOR,
                                     "status": "draft", "cases": cases,
                                     "sweep_specs": sweeps, "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": AID, "source": "Exact NRS 484B.560(7)(a)/(8) and frozen C410753 cell",
        "status": "draft", "stages": {"relevance_batch": batch_ref,
            "relevance": relevance_ref, "template": template_ref,
            "judgment_observables": observed, "bindings": binding_ref,
            "cases": cases_ref}})
    return len(cases)


if __name__ == "__main__":
    print(build())
