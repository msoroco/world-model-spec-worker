"""Author exact LVMC 11.18.020 semantic stage proposals for the frozen cell."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import school_crossing as school


HERE = Path(__file__).resolve().parent
OUT = HERE / "proposals"
AID = school.ASSIGNMENT
LAW = school.LAW
CELL = "C422976"
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
          "relevance_type": "heavy-vehicle approach to school crosswalk with an exact School-Xing sign",
          "confidence": "medium", "notes": "Municipal authority, physical display, person attempt and vehicle entry require original review."}],
        "borderline_excluded": []}
    rel_batch = write("relevance_batch.json", relevance)
    rel = write("relevance.json", relevance)
    judgments = [
        {"phrase": "approximately twelve feet", "note": "Crossing width is a measured physical fact; approximateness is unresolved."},
        {"phrase": "in the opinion of the City Traffic Engineer", "note": "Original municipal opinion is external context, not inferred from vehicle or person motion."},
        {"phrase": "conspicuous manner", "note": "Actual words, position and camera evidence are retained without a visibility cutoff."},
        {"phrase": "attempting to cross", "note": "Original person action evidence is retained without deciding legal intent."},
        {"phrase": "upon the side of the roadway on which said vehicle is coming", "note": "Relative side and approach direction are measured; legal geometric interpretation remains unresolved."},
    ]
    refs = [parameter("sign_advance_distance_ft", "world_setup", "99, 100 or 101 ft physical probes"),
            parameter("sign_displayed", "world_setup", "displayed or not displayed"),
            parameter("person_side", "world_setup", "approach_side or opposite_side"),
            parameter("person_attempt_requested", "controller", "attempt or presence only"),
            parameter("entry_requested", "controller", "hold or enter"),
            parameter("crossing_marking", "world_setup", "yellow_paint or road_buttons"),
            parameter("sign_placement", "world_setup", "curb or pavement")]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "quote": quote,
        "structure": {"law_id": LAW,
            "activation": {"condition": "Las Vegas school-vicinity intersection has an established school crossing and an actually displayed School-Xing sign governing the approach.",
                           "numeric_conditions": [{"value": 100, "unit": "ft", "operator": ">=", "variable": "sign_advance_distance_ft"}]},
            "obligation": {"description": "Operator of any vehicle does not drive into the crosswalk when a person in it on the approaching side attempts to cross.",
                           "type": "must_not", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Observe sign display, person side/attempt and heavy-vehicle body-front entry on synchronized original frames.",
                       "numeric_conditions": []},
            "judgment_calls_needed": judgments},
        "parameter_refs": refs}
    tref = write("template.json", template)
    observed = []
    for index, judgment in enumerate(judgments, 1):
        obs = {"template_id": TEMPLATE, "phrase": judgment["phrase"],
            "note": judgment["note"], "status": "draft", "observable_requirements": {
                "observables": [{"name": "original_vehicle_front", "unit": "structured",
                    "description": "Original heavy-vehicle body front relative to source-reviewed crossing."},
                    {"name": "original_person_position", "unit": "structured",
                    "description": "Original person position and movement relative to roadway and crossing."}],
                "context_inputs": [{"name": "reviewed_school_crossing_site", "unit": "source",
                    "description": "Municipal authorization, crossing dimensions, exact sign and approach direction."}],
                "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": "four_view_video", "unit": "structured",
                    "description": "Original synchronized sign, person, crossing and vehicle frames."}],
                "limitations": ["No legal cutoff or intent finding is inferred from CPU setup or fixtures."]}}
        observed.append(write(f"judgment-{index}.json", obs))
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": ["Frozen two-lane two-way travel and school_crosswalk control; original municipal site review pending."],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "reviewed_school_crossing_site", "value": "source_packet_pending",
                              "rationale": "Hold municipality, school vicinity, heavy vehicle, route and crossing geometry across linked contrasts."}],
        "variable_parameters": [dict(ref, used_by_laws=[LAW]) for ref in refs]}
    bref = write("bindings.json", binding)
    description = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())["recording_description"]
    def assignments(case):
        return {"sign_advance_distance_ft": {"kind": "world_setup", "value": case.sign_distance_ft},
                "sign_displayed": {"kind": "world_setup", "value": case.sign_displayed},
                "person_side": {"kind": "world_setup", "value": case.person_side},
                "person_attempt_requested": {"kind": "controller", "value": case.person_attempt},
                "entry_requested": {"kind": "controller", "value": case.entry_requested},
                "crossing_marking": {"kind": "world_setup", "value": case.crossing_marking},
                "sign_placement": {"kind": "world_setup", "value": case.sign_placement}}
    cases = [{"case_id": AID + "__baseline", "paired_probe_id": "baseline",
        "rationale": "Shared physical school-crossing reference; baseline is not dispatched.",
        "recording_description": description, "target_law_id": LAW,
        "target_type": "baseline", "unresolved_judgment_calls": [j["phrase"] for j in judgments],
        "variable_assignments": assignments(school.CASES[0]),
        "deliberate_differences": [p["name"] for p in refs],
        "probe": {"primary_variable": "entry_requested",
                  "comparison_or_standard": "original vehicle front at crossing",
                  "target_value_or_branch": "hold"}}]
    for case in school.CASES:
        case_id = AID + "__" + case.name
        numeric_sign_probe = case.name in ("sign_99ft_enter", "near_attempt_enter", "sign_101ft_enter")
        probe = {"primary_variable": "sign_advance_distance_ft" if numeric_sign_probe else "entry_requested",
                 "comparison_or_standard": "original sign placement relative to reviewed crossing" if numeric_sign_probe else "physical vehicle-front crossing entry with person in crossing",
                 "target_value_or_branch": case.sign_distance_ft if numeric_sign_probe else case.entry_requested}
        if numeric_sign_probe:
            probe.update({"threshold_ref": "activation.numeric_conditions[0]", "operator": ">=",
                          "unit": "ft", "test_value": case.sign_distance_ft})
        entry = {"case_id": case_id,
            "paired_probe_id": "sign_100ft_boundary" if numeric_sign_probe else case.name,
            "rationale": "Measure original School-Xing infrastructure, person action/side and heavy-vehicle entry without a legal finding.",
            "recording_description": description, "target_law_id": LAW,
            "target_type": "boundary_probe", "unresolved_judgment_calls": [j["phrase"] for j in judgments],
            "variable_assignments": assignments(case),
            "deliberate_differences": [p["name"] for p in refs],
            "probe": probe}
        if numeric_sign_probe:
            entry["epsilon_used"] = {"value": 1, "unit": "ft",
                "rationale": "One-foot sign-placement diagnostic increment around the statutory 100-foot boundary; actual placement uncertainty retained."}
        cases.append(entry)
    sweeps = [{"sweep_id": "legal_phrase_" + str(i), "target_law_id": LAW,
               "judgment_refs": [j], "status": "incomplete",
               "rationale": "Judgment meaning and training bounds are not supplied for this exact law and actor.",
               "missing_inputs": ["Original municipal or person-action measurements suitable for a reviewed phrase-specific sweep."]}
              for i, j in enumerate(judgments, 1)]
    cref = write("cases.json", {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                                "cases": cases, "sweep_specs": sweeps,
                                "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": AID, "source": "Exact LVMC 11.18.020 law and C422976 frozen cell",
        "status": "draft", "stages": {"relevance_batch": rel_batch,
            "relevance": rel, "template": tref,
            "judgment_observables": observed, "bindings": bref, "cases": cref}})
    return len(cases) - 1


if __name__ == "__main__":
    print(build())
