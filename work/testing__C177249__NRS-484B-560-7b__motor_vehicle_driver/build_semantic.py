"""Author canonical NRS 484B.560(7)(b) stages for the exact rail cell."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "proposals"
AID = HERE.name
LAW = "NRS-484B-560-7b"
CELL = "C177249"
ACTOR = "motor_vehicle_driver"
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
          "relevance_type": "motor vehicle encountering a governing device or police officer at a railroad crossing",
          "confidence": "medium", "notes": "Device officiality, officer identity, governing instruction and actual response require original source review."}],
        "borderline_excluded": []}
    batch_ref = write("relevance_batch.json", relevance)
    relevance_ref = write("relevance.json", relevance)
    judgments = [
        {"phrase": "official traffic-control device", "note": "Placement, erection authority, traffic purpose, governing movement and legal status require independent original source review."},
        {"phrase": "directions of a police officer", "note": "Actual officer identity, direction timing, governed movement and communication require independent original source review."}]
    refs = [parameter("authority_channel", "world_setup", "source-reviewed device or actual police officer"),
            parameter("instruction", "controller", "stop or permissive clear"),
            parameter("response", "controller", "halt or crossing entry"),
            parameter("crossing_geometry", "world_setup", "source-reviewed railroad grade crossing"),
            parameter("vehicle_class", "world_setup", "source-reviewed ordinary motor vehicle")]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "quote": quote,
        "structure": {"law_id": LAW,
            "activation": {"condition": "A motor vehicle driver approaches an actual railroad crossing governed by an official traffic-control device or a police officer.",
                           "numeric_conditions": []},
            "obligation": {"description": "Do not fail to obey the applicable official traffic-control device or police officer directions at the railroad crossing.",
                           "type": "must_not", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Join the original instruction history to actual vehicle body approach, entry, halt and exit; no numeric legal threshold is supplied.",
                       "numeric_conditions": []},
            "judgment_calls_needed": judgments},
        "parameter_refs": refs}
    template_ref = write("template.json", template)
    observed = []
    for index, judgment in enumerate(judgments, 1):
        obs = {"template_id": TEMPLATE, "phrase": judgment["phrase"],
            "note": judgment["note"], "status": "draft", "observable_requirements": {
                "observables": [{"name": "device_indication_history", "unit": "structured",
                    "description": "Original frame-joined actual device indication and source."},
                    {"name": "original_body_entry_exit", "unit": "structured",
                    "description": "Original vehicle body relation to reviewed crossing entry and exit."}],
                "context_inputs": [{"name": "reviewed_railway_site", "unit": "source",
                    "description": "Original crossing, official device placement and officer identity source."}],
                "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": "four_view_frame_join", "unit": "structured",
                    "description": "Original synchronized crossing, device/officer, vehicle and driver-reference views."}],
                "limitations": ["No officiality, authentic officer direction or legal verdict is inferred from a CPU fixture."]}}
        observed.append(write(f"judgment-{index}.json", obs))
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": ["Frozen paved-road railroad crossing and motor-vehicle driver; actual reviewed site pending."],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "reviewed_railway_site", "value": "source_packet_pending",
                              "rationale": "Hold actual crossing, vehicle, route, camera and duration across linked contrasts."}],
        "variable_parameters": [dict(ref, used_by_laws=[LAW]) for ref in refs]}
    binding_ref = write("bindings.json", binding)
    description = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())["recording_description"]
    cases = []
    for row in plan["cases"]:
        case_id = row["case_id"]
        name = case_id.removeprefix(AID + "__")
        authority, instruction, response = name.split("_")
        values = {"authority_channel": {"kind": "world_setup", "value": authority},
                  "instruction": {"kind": "controller", "value": instruction},
                  "response": {"kind": "controller", "value": response},
                  "crossing_geometry": {"kind": "world_setup", "value": "source-reviewed grade crossing"},
                  "vehicle_class": {"kind": "world_setup", "value": "source-reviewed ordinary motor vehicle"}}
        probe = {"primary_variable": "response",
                 "comparison_or_standard": "original instruction-to-body-response join",
                 "target_value_or_branch": response}
        entry = {"case_id": case_id,
                 "paired_probe_id": authority + "_" + instruction,
                 "rationale": row["rationale"], "recording_description": description,
                 "target_law_id": LAW, "target_type": "boundary_probe",
                 "unresolved_judgment_calls": [j["phrase"] for j in judgments],
                 "variable_assignments": values,
                 "deliberate_differences": ["authority_channel", "instruction", "response"],
                 "probe": probe}
        cases.append(entry)
    sweeps = [{"sweep_id": "legal_phrase_" + str(i), "target_law_id": LAW,
               "judgment_refs": [j], "status": "incomplete",
               "rationale": "No exact-law accepted judgment-range bounds or physical source outcome are supplied.",
               "missing_inputs": ["Original officiality, officer direction and instruction-response evidence suitable for reviewed phrase-specific physical coverage."]}
              for i, j in enumerate(judgments, 1)]
    cases_ref = write("cases.json", {"cell_id": CELL, "actor": ACTOR,
                                     "status": "draft", "cases": cases,
                                     "sweep_specs": sweeps, "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": AID, "source": "Exact NRS 484B.560(7)(b) and frozen C177249 cell",
        "status": "draft", "stages": {"relevance_batch": batch_ref,
            "relevance": relevance_ref, "template": template_ref,
            "judgment_observables": observed, "bindings": binding_ref,
            "cases": cases_ref}})
    return len(cases)


if __name__ == "__main__":
    print(build())
