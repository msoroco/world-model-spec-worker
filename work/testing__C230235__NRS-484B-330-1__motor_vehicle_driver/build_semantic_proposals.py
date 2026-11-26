"""Draft exact-law canonical stages while leaving original judgments unresolved."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from flagger_zone import CASES
from source_packet import ASSIGNMENT


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = "NRS-484B-330-1"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
JUDGMENTS = [
    ("authorized flagger", "Authorization requires an independently reviewed source.", "flagger_authorization"),
    ("serving in a traffic control capacity", "Original role and timing require source review.", "traffic_control_role"),
    ("designated as a temporary traffic control zone", "Designation and boundaries are separate from visual markings.", "zone_designation"),
    ("clearly marked area of highway construction or maintenance", "Construction or maintenance and clear marking need separate original sources.", "construction_marking"),
    ("any signal", "Original content, orientation, visibility and recipient remain source-bound.", "signal_content"),
    ("fail or refuse to comply", "Observed vehicle motion does not itself decide this legal judgment.", "vehicle_motion"),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(folder: Path, name: str, value: dict) -> dict:
    path = folder / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return {"path": "proposals/" + name, "sha256": sha(path)}


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.diagnostic.json").read_text())
    assignment = json.loads((ROOT / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    quote = assignment["law"]["text"]
    if quote != plan["law_text"]:
        raise ValueError("exact frozen law quote changed")
    descriptions = {entry["case_id"]: json.loads((HERE / entry["construction"]).read_text())[
        "recording_description"] for entry in manifest["cases"]}
    folder = HERE / "proposals"
    folder.mkdir(exist_ok=True)
    relevance = {"status": "draft", "cell_id": "C230235", "actor": ACTOR,
                 "relevant_laws": [{"law_id": LAW, "quote": quote,
                                    "applies_to": [ACTOR], "confidence": "low",
                                    "relevance_type": "authorized flagger in marked construction or designated temporary zone",
                                    "notes": "Original authorization, marking or designation, signal and recipient need reviewed sources."}],
                 "borderline_excluded": []}
    refs = {"relevance_batch": write(folder, "relevance_batch.json", relevance),
            "relevance": write(folder, "relevance.json", relevance)}
    parameters = [
        {"name": "driver_response", "kind": "controller",
         "range_or_domain": "source-measured stop or continue motion under active signal"},
        {"name": "zone_designation", "kind": "world_setup",
         "range_or_domain": "independently reviewed designation and zone boundaries"},
        {"name": "marked_construction", "kind": "world_setup",
         "range_or_domain": "independently reviewed highway construction or maintenance and clear marking"},
        {"name": "flagger_authorization", "kind": "world_setup",
         "range_or_domain": "independently reviewed flagger authorization and role"},
        {"name": "signal_content", "kind": "world_setup",
         "range_or_domain": "source-reviewed stop or proceed signal, orientation and recipient"},
        {"name": "reviewed_site", "kind": "world_setup",
         "range_or_domain": "one original reviewed C230235 highway site and OpenDRIVE map"},
        {"name": "capture_profile", "kind": "world_setup",
         "range_or_domain": "four original cameras, 20 Hz, 900 frames"},
    ]
    template = {"status": "draft", "law_id": LAW, "actor": ACTOR,
                "template_id": TEMPLATE, "quote": quote,
                "structure": {"activation": {"condition": "Driver in clearly marked highway construction or maintenance, or a designated temporary traffic control zone.",
                                              "numeric_conditions": []},
                              "obligation": {"type": "comply", "description": "Comply with a governing signal of an authorized traffic-control flagger.",
                                             "numeric_conditions": []},
                              "exceptions": [],
                              "timing": {"description": "Original active signal, release and driver response history.",
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
                        "observables": [{"name": "original_vehicle_motion", "unit": "structured",
                                         "description": "Retained original vehicle positions and speed."}],
                        "context_inputs": [need], "sweep_dimensions": [],
                        "landmarks": [], "recording_needs": [need],
                        "limitations": ["Source-shaped fixtures do not establish legal compliance."]}}
        judgment_refs.append(write(folder, f"judgment-{index}.json", proposal))
    refs["judgment_observables"] = judgment_refs
    binding = {"status": "draft", "cell_id": "C230235", "actor": ACTOR,
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "context_refs": [],
               "established_contexts": ["Frozen flagger road cell identity; original site remains source-gated."],
               "fixed_parameters": [{"name": "assigned_cell", "value": "C230235",
                                     "rationale": "Frozen catalog identity, not a reviewed physical site."}],
               "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in parameters]}
    refs["bindings"] = write(folder, "bindings.json", binding)
    base = {item["name"]: {"kind": item["kind"], "value": {
        "driver_response": "continue", "zone_designation": "designated",
        "marked_construction": "not_marked_construction",
        "flagger_authorization": "authorized", "signal_content": "stop",
        "reviewed_site": "original C230235 source packet required",
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
        assignments["driver_response"]["value"] = case.response
        assignments["zone_designation"]["value"] = "designated" if case.designated else "not_designated"
        assignments["marked_construction"]["value"] = "marked_construction" if case.marked_construction else "not_marked_construction"
        assignments["flagger_authorization"]["value"] = "authorized" if case.authorized else "not_authorized"
        assignments["signal_content"]["value"] = case.signal
        changed = [name for name in assignments if assignments[name]["value"] != base[name]["value"]]
        if not changed:
            changed = ["driver_response"]
        cid = ASSIGNMENT + "__" + case.name
        cases.append({"case_id": cid, "target_law_id": LAW,
                      "target_type": "boundary_probe", "paired_probe_id": "flagger_zone",
                      "deliberate_differences": changed,
                      "probe": {"primary_variable": changed[0],
                                "comparison_or_standard": "case-plan.json",
                                "target_value_or_branch": case.name},
                      "rationale": "Controlled original-source flagger, zone, signal and response contrast.",
                      "recording_description": descriptions[cid],
                      "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
                      "variable_assignments": assignments})
    sweeps = [{"sweep_id": "pending-" + str(index), "target_law_id": LAW,
               "judgment_refs": [{"phrase": phrase, "note": note}],
               "status": "incomplete", "missing_inputs": ["Reviewed source observation and feasible engineering range"],
               "rationale": "No engineering value is a statutory cutoff."}
              for index, (phrase, note, _) in enumerate(JUDGMENTS, 1)]
    refs["cases"] = write(folder, "cases.json", {
        "status": "draft", "cell_id": "C230235", "actor": ACTOR,
        "cases": cases, "sweep_specs": sweeps, "sweeps_expanded": False})
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
             "stages": refs}
    (folder / "semantic-index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    return {"selected_cases": len(CASES), "stage_count": 5 + len(JUDGMENTS),
            "index_sha256": sha(folder / "semantic-index.json")}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
