"""Author the canonical C111610 crosswalk stage proposal chain."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_inline import description


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "proposals"
PLAN = json.loads((ROOT / "case-plan.json").read_text())
AID = PLAN["assignment_id"]
LAW = PLAN["law_id"]
ACTOR = PLAN["actor"]
QUOTE = PLAN["law_text"]


def write(name, data):
    OUT.mkdir(exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(data, indent=2) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def named(name, explanation):
    return {"name": name, "unit": "structured record", "description": explanation}


def build():
    relevance = {"cell_id": "C111610", "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
            "applies_to": [ACTOR], "relevance_type": "direct crosswalk right-of-way duty for turning driver",
            "confidence": "high", "notes": "Frozen C111610 left turn with a pedestrian."}],
        "borderline_excluded": []}
    refs = {"relevance_batch": write("relevance_batch.json", relevance),
            "relevance": write("relevance.json", relevance)}
    phrases = [
        "not in place or not in operation",
        "slowing down or stopping if need be so to yield",
        "approaching so closely from the opposite half of the highway as to be in danger",
        QUOTE.split(":", 1)[0],
    ]
    notes = [
        "Complete relevant official-device inventory and original state history are required; absence of one actor is insufficient.",
        "Original ego brake/motion and pedestrian crossing context are measured; need and right of way receive independent review.",
        "Original relative motion and geometry are retained without a numeric legal danger cutoff.",
        "Independent source-backed applicability review controls the introductory exceptions.",
    ]
    variables = [
        ("pedestrian_half", "world_setup", "destination, opposite, or outside directional half"),
        ("crosswalk_position", "world_setup", "in crosswalk, outside crosswalk, or clear"),
        ("official_device_condition", "world_setup", "absent, not operating, or operating"),
        ("pedestrian_approach", "controller", "source-reviewed relative route timing; no legal cutoff"),
        ("ego_turn_route", "world_setup", "same connected original left turn"),
    ]
    template_id = LAW + "@" + ACTOR
    template = {"template_id": template_id, "law_id": LAW, "actor": ACTOR,
        "quote": QUOTE,
        "structure": {"law_id": LAW,
            "activation": {"condition": "Official traffic-control devices are not in place or not in operation, and a pedestrian crosses within a crosswalk on the destination half or approaches from the opposite half so closely as to be in danger.", "numeric_conditions": []},
            "obligation": {"description": "Turning driver yields right of way, slowing or stopping if need be, subject to the stated exceptions.", "type": "must", "numeric_conditions": []},
            "exceptions": [{"trigger": "A source-reviewed NRS 484B.287, 484B.290 or 484B.350 exception applies.",
                            "effect": "The exact overlapping provision governs after independent review.",
                            "replacement_obligation": "No categorical legal verdict is inferred from this construction.",
                            "source_clause": QUOTE.split(":", 1)[0]}],
            "timing": {"description": "Original Native frames join device state, pedestrian crossing position and ego turn/brake throughout the attempt.", "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                      for phrase, note in zip(phrases, notes)]},
        "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                           for name, kind, domain in variables]}
    refs["template"] = write("template.json", template)
    observations = [named(row["name"], row["source"]) for row in PLAN["observations"]]
    contexts = [named("reviewed_original_site", "Original map, crosswalk, all directional lanes and device inventory."),
                named("reviewed_exception_context", "Independent applicability sources for the three cited exceptions.")]
    refs["judgment_observables"] = []
    for index, (phrase, note) in enumerate(zip(phrases, notes), 1):
        payload = {"template_id": template_id, "phrase": phrase, "note": note,
            "status": "draft", "observable_requirements": {
                "observables": observations, "context_inputs": contexts,
                "sweep_dimensions": [], "landmarks": [],
                "recording_needs": observations,
                "limitations": ["No legal cutoff or verdict is supplied by this proposal.",
                                "Original site, device, pedestrian and ego measurements need local review."]}}
        refs["judgment_observables"].append(write(f"judgment-{index}.json", payload))
    binding = {"cell_id": "C111610", "actor": ACTOR, "status": "draft",
        "established_contexts": ["intersection", "turn", "pedestrian"],
        "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": name, "kind": kind,
                                 "range_or_domain": domain, "used_by_laws": [LAW]}
                                for name, kind, domain in variables]}
    refs["bindings"] = write("bindings.json", binding)
    recording = description(PLAN)
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Reference left-turn geometry; no selected recording.",
                "variable_assignments": {name: {"kind": kind, "value": "reference",
                                                  "note": "No legal result inferred."}
                                         for name, kind, _ in variables},
                "recording_description": recording,
                "unresolved_judgment_calls": phrases}
    selected = []
    for case in PLAN["cases"]:
        changes = case["comparison_variables"]
        assignments = {name: {"kind": kind,
                              "value": changes.get(name, "same reviewed left turn"),
                              "note": "Source-bound physical setup; legal judgment unresolved."}
                       for name, kind, _ in variables}
        selected.append({"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "boundary_probe", "rationale": case["purpose"],
            "variable_assignments": assignments, "recording_description": recording,
            "unresolved_judgment_calls": phrases,
            "paired_probe_id": case["case_id"].rsplit("__", 1)[-1],
            "deliberate_differences": list(changes),
            "probe": {"primary_variable": "pedestrian_half",
                      "comparison_or_standard": "controlled exact crosswalk case plan",
                      "target_value_or_branch": case["purpose"]}})
    refs["cases"] = write("cases.json", {"cell_id": "C111610", "actor": ACTOR,
        "status": "draft", "cases": [baseline, *selected],
        "sweep_specs": [{"sweep_id": "crosswalk_original_sources_pending",
            "target_law_id": LAW, "status": "incomplete",
            "judgment_refs": [{"phrase": phrase, "note": note}
                              for phrase, note in zip(phrases, notes)],
            "rationale": "Original physical site, device states, exception applicability and motion are required before freezing judgment sweep axes.",
            "missing_inputs": ["Original reviewed crosswalk and directional-half geometry",
                               "Complete original official-device state history",
                               "Source-reviewed exception applicability",
                               "Original native turn and pedestrian trajectories"]}],
        "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": AID, "stages": refs})
    return refs


if __name__ == "__main__":
    build()
    print("authored seven selected semantic cases and four judgment phrases")
