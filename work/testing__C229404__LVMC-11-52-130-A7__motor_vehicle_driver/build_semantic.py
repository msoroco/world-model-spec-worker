"""Author exact LVMC driveway duty and exception semantic proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "proposals"
REPO = ROOT.parents[1]
JUDGMENTS = (
    ("in front of or within five feet of a public or private driveway",
     "The statute supplies five feet; frontage and measurement convention require source review."),
    ("necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device",
     "Necessity and governing direction require retained original event and authority sources."),
    ("owns or is in control of that driveway, or who is a family member or invitee",
     "Private driveway relationship is an exception for parking only."),
    ("United States Postal Service vehicle while it is being operated on official business",
     "Postal status and official business require independent original records."),
)
VARIABLES = ("driveway_kind", "activity", "position_target", "driver_relationship",
             "necessity_or_postal_context")


def write(name, value):
    path = OUT / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment_path = REPO / "inputs" / ROOT.name / "assignment.json"
    assignment = json.loads(assignment_path.read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    description = json.loads((ROOT / "config.json").read_text())["recording_description"]
    law, actor, cell = assignment["law_id"], assignment["actor"], assignment["cell_id"]
    template_id = law + "@" + actor
    quote = assignment["law"]["text"]
    relevance = {"cell_id": cell, "actor": actor, "status": "draft",
                 "relevant_laws": [{"law_id": law, "quote": quote, "applies_to": [actor],
                                    "relevance_type": "conditional driveway stop, stand or park duty with private and postal exceptions",
                                    "confidence": "low",
                                    "notes": "Actual driveway, frontage, relationship, necessity and postal facts require original source review."}],
                 "borderline_excluded": []}
    rel_batch = write("relevance_batch.json", relevance)
    rel = write("relevance.json", relevance)
    params = [{"name": name, "kind": "controller" if name in ("activity", "position_target")
               else "world_setup", "range_or_domain": ", ".join(sorted({str(c[name]) for c in plan["cases"]}))}
              for name in VARIABLES]
    template = {"template_id": template_id, "law_id": law, "actor": actor, "quote": quote,
                "structure": {"law_id": law,
                              "activation": {"condition": "Vehicle stops, stands or parks at a source-reviewed public or private driveway mouth.",
                                             "numeric_conditions": []},
                              "obligation": {"description": "Do not stop, stand or park in front of or within five feet of the driveway, subject to the exact source exceptions.",
                                             "type": "must_not", "numeric_conditions": []},
                              "exceptions": [
                                  {"trigger": "Necessary to avoid traffic conflict in compliance with law or police/device direction",
                                   "effect": "The stop, stand or park prohibition does not apply in the supported necessity context",
                                   "replacement_obligation": "No blanket parking permission inferred",
                                   "source_clause": "except when necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device"},
                                  {"trigger": "Parking in or near a private driveway by its owner/controller, family member or invitee",
                                   "effect": "The driveway provision does not apply to that parking",
                                   "replacement_obligation": "The exception does not extend to stopping or standing",
                                   "source_clause": "this provision does not apply to the parking of a vehicle in or near a private driveway by a person who owns or is in control of that driveway, or who is a family member or invitee"},
                                  {"trigger": "USPS vehicle operated on official business",
                                   "effect": "Paragraph (7) does not apply",
                                   "replacement_obligation": "No personal postal exception inferred",
                                   "source_clause": "do not apply to a United States Postal Service vehicle while it is being operated on official business"}],
                              "timing": {"description": "Original 45-second stop, stand or park episode and settled activity window.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                                        for phrase, note in JUDGMENTS]},
                "parameter_refs": params}
    template_ref = write("template.json", template)
    observables = [{"name": c["name"], "unit": c["unit"], "description": c["method"]}
                   for c in description["channels"]]
    context = [{"name": c["name"], "unit": c["unit"], "description": c["method"]}
               for c in description["context_inputs"]]
    judgments = []
    for index, (phrase, note) in enumerate(JUDGMENTS, 1):
        judgments.append(write(f"judgment-{index}.json",
                               {"template_id": template_id, "phrase": phrase, "note": note,
                                "status": "draft", "observable_requirements": {
                                    "observables": observables, "context_inputs": context,
                                    "sweep_dimensions": [{"name": name, "unit": "categorical",
                                                          "description": "Exact planned source-reviewed contrast"}
                                                         for name in VARIABLES],
                                    "landmarks": [], "recording_needs": observables,
                                    "limitations": ["Original source review and Native physical realization pending.",
                                                    "Five-foot mouth distance is an engineering proxy until measurement convention is reviewed."]}}))
    binding = {"cell_id": cell, "actor": actor, "status": "draft",
               "established_contexts": ["road layout", "driveway entrance", "vehicle stop, stand or park task"],
               "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [dict(p, used_by_laws=[law]) for p in params]}
    binding_ref = write("bindings.json", binding)
    def variable(name, value):
        return {"kind": "controller" if name in ("activity", "position_target")
                else "world_setup", "value": value,
                "note": "Exact source-reviewed condition; no legal outcome label"}
    cases = [{"case_id": plan["assignment_id"] + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Shared source-reviewed driveway and road reference",
              "variable_assignments": {name: variable(name, plan["cases"][0][name]) for name in VARIABLES},
              "unresolved_judgment_calls": [phrase for phrase, _ in JUDGMENTS],
              "recording_description": description}]
    for row in plan["cases"]:
        cases.append({"case_id": row["case_id"], "target_law_id": law,
                      "target_type": "boundary_probe", "status": "draft",
                      "rationale": "Original geometry, activity and exception context with legal judgment unresolved.",
                      "paired_probe_id": "exact_driveway_controls",
                      "variable_assignments": {name: variable(name, row[name]) for name in VARIABLES},
                      "unresolved_judgment_calls": [phrase for phrase, _ in JUDGMENTS],
                      "deliberate_differences": list(VARIABLES),
                      "probe": {"primary_variable": "position_target",
                                "comparison_or_standard": "Original full footprint, reviewed mouth and exact exception facts",
                                "target_value_or_branch": row["position_target"]},
                      "recording_description": description})
    sweep = {"sweep_id": "c229404-driveway-qualitative-exceptions",
             "target_law_id": law,
             "judgment_refs": [{"phrase": phrase, "note": note} for phrase, note in JUDGMENTS],
             "status": "incomplete",
             "rationale": "Original Native and reviewed driveway, necessity, relationship and postal records absent.",
             "missing_inputs": ["Reviewed original driveway and authority facts", "Native physical activity and pixels"]}
    cases_ref = write("cases.json", {"cell_id": cell, "actor": actor, "status": "draft",
                                     "cases": cases, "sweep_specs": [sweep], "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": plan["assignment_id"],
                                  "stages": {"relevance_batch": rel_batch, "relevance": rel,
                                             "template": template_ref,
                                             "judgment_observables": judgments,
                                             "bindings": binding_ref, "cases": cases_ref}})
    print("LVMC driveway duty, three exceptions and 16 exact semantic probes authored")


if __name__ == "__main__":
    main()
