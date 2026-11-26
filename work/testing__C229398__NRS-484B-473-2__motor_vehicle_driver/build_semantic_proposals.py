"""Draft exact-law canonical stages while leaving original judgments unresolved."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parked_lamps import CASES
from source_packet import ASSIGNMENT


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = "NRS-484B-473-2"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
JUDGMENTS = [
    ("lights are displayed", "Displayed-light state requires original lamp telemetry.", "displayed_lights"),
    ("lawfully parked", "Parking lawfulness requires separate highway and parking context sources.", "parking_lawfulness"),
    ("at nighttime upon any highway", "Night and highway status require independent original sources.", "nighttime"),
    ("depressed or dimmed", "Beam state must be observed without inventing a numeric legal cutoff.", "beam_aim"),
    ("cowl or parking lamps are not used", "Auxiliary lamp use is separate from displayed beam state.", "cowl_lamp"),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(folder: Path, name: str, value: dict) -> dict:
    path = folder / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return {"path": "proposals/" + name, "sha256": sha(path)}


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    assignment = json.loads((ROOT / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    quote = assignment["law"]["text"]
    if quote != plan["law_text"]:
        raise ValueError("exact frozen law quote changed")
    descriptions = {entry["case_id"]: json.loads((HERE / entry["construction"]).read_text())[
        "recording_description"] for entry in manifest["cases"]}
    folder = HERE / "proposals"
    folder.mkdir(exist_ok=True)
    relevance = {"status": "draft", "cell_id": "C229398", "actor": ACTOR,
                 "relevant_laws": [{"law_id": LAW, "quote": quote,
                                    "applies_to": [ACTOR], "confidence": "low",
                                    "relevance_type": "parked vehicle lights at nighttime on a highway",
                                    "notes": "Original lawful parking, night, highway and lamp states need reviewed sources."}],
                 "borderline_excluded": []}
    refs = {"relevance_batch": write(folder, "relevance_batch.json", relevance),
            "relevance": write(folder, "relevance.json", relevance)}
    parameters = [
        {"name": "lamp_mode", "kind": "controller",
         "range_or_domain": "source-observed undimmed or dimmed displayed beam"},
        {"name": "auxiliary_lamp", "kind": "controller",
         "range_or_domain": "source-observed none, cowl or parking lamp use"},
        {"name": "night", "kind": "world_setup",
         "range_or_domain": "reviewed original nighttime or daytime context"},
        {"name": "lawful_park", "kind": "world_setup",
         "range_or_domain": "reviewed original lawful or unlawful parking context"},
        {"name": "reviewed_site", "kind": "world_setup",
         "range_or_domain": "one original reviewed C229398 highway site and OpenDRIVE map"},
        {"name": "capture_profile", "kind": "world_setup",
         "range_or_domain": "four original cameras, 20 Hz, 900 frames"},
    ]
    template = {"status": "draft", "law_id": LAW, "actor": ACTOR,
                "template_id": TEMPLATE, "quote": quote,
                "structure": {"activation": {"condition": "Lights displayed on a vehicle lawfully parked at nighttime upon a highway while cowl and parking lamps are not used.",
                                              "numeric_conditions": []},
                              "obligation": {"type": "comply", "description": "Displayed lights shall be depressed or dimmed in the stated conditions.",
                                             "numeric_conditions": []},
                              "exceptions": [],
                              "timing": {"description": "Original parked interval and lamp-state history.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                                        for phrase, note, _ in JUDGMENTS]},
                "parameter_refs": parameters}
    refs["template"] = write(folder, "template.json", template)
    judgment_refs = []
    for index, (phrase, note, source_name) in enumerate(JUDGMENTS, 1):
        need = {"name": source_name, "unit": "structured",
                "description": "Original source-bound finding for " + phrase}
        proposal = {"status": "draft", "template_id": TEMPLATE,
                    "phrase": phrase, "note": note,
                    "observable_requirements": {
                        "observables": [{"name": "lamp_state", "unit": "structured",
                                         "description": "Retained original lamp and beam state."}],
                        "context_inputs": [need], "sweep_dimensions": [],
                        "landmarks": [], "recording_needs": [need],
                        "limitations": ["Source-shaped fixtures do not establish legal compliance."]}}
        judgment_refs.append(write(folder, f"judgment-{index}.json", proposal))
    refs["judgment_observables"] = judgment_refs
    binding = {"status": "draft", "cell_id": "C229398", "actor": ACTOR,
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "context_refs": [],
               "established_contexts": ["Frozen parked-road cell identity; original site remains source-gated."],
               "fixed_parameters": [{"name": "assigned_cell", "value": "C229398",
                                     "rationale": "Frozen catalog identity, not a reviewed physical site."}],
               "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in parameters]}
    refs["bindings"] = write(folder, "bindings.json", binding)
    base = {item["name"]: {"kind": item["kind"], "value": {
        "lamp_mode": "undimmed", "auxiliary_lamp": "none",
        "night": "night", "lawful_park": "lawful",
        "reviewed_site": "original C229398 source packet required",
        "capture_profile": "four original cameras, 20 Hz, 900 frames"}[item["name"]]}
        for item in parameters}
    description = next(iter(descriptions.values()))
    cases = [{"case_id": ASSIGNMENT + "__semantic_baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Shared source-dependent setup; no additional recording.",
              "recording_description": description,
              "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
              "variable_assignments": base}]
    for case in CASES:
        assignments = json.loads(json.dumps(base))
        assignments["lamp_mode"]["value"] = case.lamp_mode
        assignments["auxiliary_lamp"]["value"] = case.auxiliary_lamp
        assignments["night"]["value"] = "night" if case.night else "day"
        assignments["lawful_park"]["value"] = "lawful" if case.lawful_park else "unlawful"
        changed = [name for name in assignments if assignments[name]["value"] != base[name]["value"]]
        if not changed:
            changed = ["lamp_mode"]
        cid = ASSIGNMENT + "__" + case.name
        cases.append({"case_id": cid, "target_law_id": LAW,
                      "target_type": "boundary_probe", "paired_probe_id": "parked_lamps",
                      "deliberate_differences": changed,
                      "probe": {"primary_variable": changed[0],
                                "comparison_or_standard": "case-plan.json",
                                "target_value_or_branch": case.name},
                      "rationale": "Controlled original-source parking, nighttime and lamp-state contrast.",
                      "recording_description": descriptions[cid],
                      "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
                      "variable_assignments": assignments})
    sweeps = [{"sweep_id": "pending-" + str(index), "target_law_id": LAW,
               "judgment_refs": [{"phrase": phrase, "note": note}],
               "status": "incomplete", "missing_inputs": ["Reviewed source observation and feasible engineering range"],
               "rationale": "No engineering value is a statutory cutoff."}
              for index, (phrase, note, _) in enumerate(JUDGMENTS, 1)]
    refs["cases"] = write(folder, "cases.json", {
        "status": "draft", "cell_id": "C229398", "actor": ACTOR,
        "cases": cases, "sweep_specs": sweeps, "sweeps_expanded": True})
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
             "stages": refs}
    (folder / "semantic-index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    return {"selected_cases": len(CASES), "stage_count": 5 + len(JUDGMENTS),
            "index_sha256": sha(folder / "semantic-index.json")}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
