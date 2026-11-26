"""Draft the exact hose law's source-bound canonical semantic stages."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
LAW = "NRS-484B-913"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
JUDGMENTS = (
    ("unprotected hose", "Original protection arrangement and actual hose identity require review.", "hose_protection"),
    ("for use at any fire or alarm of fire or practice runs", "Department purpose must be established by an original incident source.", "incident_purpose"),
    ("official in command", "Original command appointment and identity require review.", "command_official"),
    ("consent", "Communication source, scope, timing and authority require review.", "consent_source"),
)


def write(directory, name, value):
    path = directory / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    assignment = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    quote = assignment["law"]["text"]
    directory = HERE / "proposals"
    directory.mkdir(exist_ok=True)
    relevance = {"status": "draft", "cell_id": "C197786", "actor": ACTOR,
                 "relevant_laws": [{"law_id": LAW, "quote": quote,
                                    "applies_to": [ACTOR], "confidence": "low",
                                    "relevance_type": "crossing a fire-department hose on a private way",
                                    "notes": "Original hose, incident, command and passage sources remain pending."}],
                 "borderline_excluded": []}
    stages = {"relevance_batch": write(directory, "relevance_batch.json", relevance),
              "relevance": write(directory, "relevance.json", relevance)}
    parameters = [
        {"name": "incident_purpose", "kind": "world_setup", "range_or_domain": "fire, alarm or practice"},
        {"name": "hose_protection", "kind": "world_setup", "range_or_domain": "source-reviewed unprotected or protected"},
        {"name": "command_consent", "kind": "world_setup", "range_or_domain": "none, given or withheld by official in command"},
        {"name": "planned_hose_crossing", "kind": "controller", "range_or_domain": "crossing or avoidance route; actual body contact measured"},
        {"name": "reviewed_private_way", "kind": "world_setup", "range_or_domain": "one original C197786 private way and hose"},
    ]
    template = {"status": "draft", "template_id": TEMPLATE, "law_id": LAW,
                "actor": ACTOR, "quote": quote,
                "structure": {
                    "activation": {"condition": "A human driver drives an ordinary vehicle over an actual fire-department hose laid on the assigned private way for a qualifying fire, alarm or practice purpose.", "numeric_conditions": []},
                    "obligation": {"type": "prohibition", "description": "Do not drive over the unprotected hose without consent of the fire department official in command.", "numeric_conditions": []},
                    "exceptions": [{"source_clause": "without the consent of the fire department official in command",
                                    "trigger": "source-established consent of that official, effective before physical passage and scoped to it",
                                    "effect": "the stated without-consent condition is absent",
                                    "description": "A gesture or stated scenario label alone is insufficient."}],
                    "timing": {"description": "Original consent interval relative to each original body-over-hose frame.", "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                              for phrase, note, _ in JUDGMENTS]},
                "parameter_refs": parameters}
    stages["template"] = write(directory, "template.json", template)
    judgments = []
    for index, (phrase, note, observable) in enumerate(JUDGMENTS, 1):
        observation = {"name": observable, "unit": "structured",
                       "description": "Original source and observation for " + phrase + "."}
        proposal = {"status": "draft", "template_id": TEMPLATE, "phrase": phrase, "note": note,
                    "observable_requirements": {"observables": [observation],
                                                "context_inputs": [{"name": "reviewed_original_site", "unit": "structured",
                                                                    "description": "Source-hashed private way and Native hose placement."}],
                                                "sweep_dimensions": [], "landmarks": [],
                                                "recording_needs": [observation],
                                                "limitations": ["Diagnostic fixtures cannot establish original legal applicability."]}}
        judgments.append(write(directory, f"judgment-{index}.json", proposal))
    stages["judgment_observables"] = judgments
    binding = {"status": "draft", "cell_id": "C197786", "actor": ACTOR,
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "context_refs": [], "established_contexts": ["Frozen C197786 catalog cell; original site remains source-gated."],
               "fixed_parameters": [{"name": "assigned_cell", "value": "C197786",
                                     "rationale": "Frozen catalog identity, not reviewed physical placement."}],
               "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in parameters]}
    stages["bindings"] = write(directory, "bindings.json", binding)
    names = ("original_ego_body_footprint", "actual_hose_segment", "hose_protection",
             "incident_purpose", "command_official", "consent_source", "private_way_access")
    description = {"channels": [{"name": name, "unit": "structured",
                                 "method": "Original source-hashed Native or reviewed source observation joined by frame",
                                 "time_window": "all 900 original world ticks", "reference_frame": "reviewed C197786 Native map",
                                 "sampling_rate_hz": 20, "uncertainty": "physical realization and legal interpretation pending"}
                                for name in names],
                   "context_inputs": [{"name": "reviewed_original_site", "unit": "structured",
                                       "method": "retained original private-way, incident and hose inventory"}],
                   "limitations": ["Commanded crossing and a synthetic hose cannot prove actual body passage or legal outcome."]}
    baseline = {"incident_purpose": {"kind": "world_setup", "value": "fire"},
                "hose_protection": {"kind": "world_setup", "value": "unprotected"},
                "command_consent": {"kind": "world_setup", "value": "none"},
                "planned_hose_crossing": {"kind": "controller", "value": True},
                "reviewed_private_way": {"kind": "world_setup", "value": "reviewed C197786 original site"}}
    cases = [{"case_id": ASSIGNMENT + "__semantic_baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Shared site context; no separate recording.",
              "recording_description": description,
              "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
              "variable_assignments": baseline}]
    for item in plan["cases"]:
        values = json.loads(json.dumps(baseline))
        for key in ("incident_purpose", "hose_protection", "command_consent", "planned_hose_crossing"):
            values[key]["value"] = item[key]
        changed = [key for key in values if values[key]["value"] != baseline[key]["value"]]
        cases.append({"case_id": item["case_id"], "target_law_id": LAW,
                      "target_type": "boundary_probe", "paired_probe_id": "hose_statutory_contrasts",
                      "deliberate_differences": changed,
                      "probe": {"primary_variable": changed[0] if changed else "planned_hose_crossing",
                                "comparison_or_standard": "exact statutory hose/protection/consent/passage/purpose case plan",
                                "target_value_or_branch": item["case_id"].split("__")[-1]},
                      "rationale": "Original source and body footprint decide observed branch; no legal verdict is encoded.",
                      "recording_description": description,
                      "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
                      "variable_assignments": values})
    sweeps = []
    stages["cases"] = write(directory, "cases.json",
                            {"status": "draft", "cell_id": "C197786", "actor": ACTOR,
                             "cases": cases, "sweep_specs": sweeps, "sweeps_expanded": True})
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT, "stages": stages}
    (directory / "semantic-index.json").write_text(json.dumps(index, indent=2) + "\n")
    return {"stage_count": 9, "selected_cases": len(plan["cases"]), "status": "draft"}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
