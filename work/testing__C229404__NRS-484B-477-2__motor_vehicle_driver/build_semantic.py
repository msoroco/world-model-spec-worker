"""Author the exact NRS alley-access semantic stage proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "proposals"


def write(name, value):
    path = OUT / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def variable(kind, value, note):
    return {"kind": kind, "value": value, "note": note}


def main():
    assignment = json.loads((ROOT.parent.parent / "inputs" / ROOT.name /
                             "assignment.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    description = json.loads((ROOT / "config.json").read_text())["recording_description"]
    law, cell, actor = assignment["law_id"], assignment["cell_id"], assignment["actor"]
    quote = assignment["law"]["text"]
    template_id = law + "@" + actor
    relevance = {"cell_id": cell, "actor": actor, "status": "draft",
                 "relevant_laws": [{"law_id": law, "quote": quote,
                                    "applies_to": [actor],
                                    "relevance_type": "conditional alley parking and abutting-property access duty",
                                    "confidence": "low",
                                    "notes": "Fixed road/park/driveway_entrance task; qualifying alley and abutting property require independent original-source review."}],
                 "borderline_excluded": []}
    rel_batch_ref = write("relevance_batch.json", relevance)
    rel_ref = write("relevance.json", relevance)
    phrase = "block the driveway or entrance to any abutting property"
    note = "No numeric statutory blocking cutoff; original footprint, access geometry and permitted vehicular use require review."
    params = [{"name": "access_kind", "kind": "world_setup",
               "range_or_domain": "driveway or entrance to abutting property"},
              {"name": "parking_position", "kind": "controller",
               "range_or_domain": "clear or overlapping source-surveyed access corridor; no legal label"}]
    template = {"template_id": template_id, "law_id": law, "actor": actor,
                "quote": quote,
                "structure": {"law_id": law,
                              "activation": {"condition": "A person stops, stands or parks a vehicle within a legally qualifying alley.",
                                             "numeric_conditions": []},
                              "obligation": {"description": "Must not place that vehicle so as to block the driveway or entrance to abutting property.",
                                             "type": "must_not", "numeric_conditions": []},
                              "exceptions": [],
                              "timing": {"description": "Original stopping, standing and parking episode while the vehicle is positioned in the alley.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": phrase, "note": note}]},
                "parameter_refs": params}
    template_ref = write("template.json", template)
    observables = [{"name": c["name"], "unit": c["unit"],
                    "description": c["method"]} for c in description["channels"]]
    context = [{"name": c["name"], "unit": c["unit"],
                "description": c["method"]} for c in description["context_inputs"]]
    judgment = {"template_id": template_id, "phrase": phrase, "note": note,
                "status": "draft", "observable_requirements": {
                    "observables": observables, "context_inputs": context,
                    "sweep_dimensions": [{"name": "parking_position", "unit": "categorical",
                                          "description": "Source-surveyed clear or overlapping body placement, not legal blocking labels."}],
                    "landmarks": [], "recording_needs": observables,
                    "limitations": ["Alley/highway and abutting-property legal status require independent source review.",
                                    "Engineering body/access intersection does not define statutory blocking."]}}
    judgment_ref = write("judgment-1.json", judgment)
    bindings = {"cell_id": cell, "actor": actor, "status": "draft",
                "established_contexts": ["road layout", "vehicle parking task", "driveway or entrance control"],
                "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
                "context_refs": [], "fixed_parameters": [],
                "variable_parameters": [dict(p, used_by_laws=[law]) for p in params]}
    binding_ref = write("bindings.json", bindings)
    cases = [{"case_id": plan["assignment_id"] + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Shared surveyed alley and abutting-property access reference; no legal outcome label.",
              "variable_assignments": {"access_kind": variable("world_setup", "driveway", "Reference access kind"),
                                       "parking_position": variable("controller", "clear", "Reference source-surveyed position")},
              "unresolved_judgment_calls": [phrase],
              "recording_description": description}]
    for row in plan["cases"]:
        kind, position = row["access_kind"], row["parking_position"]
        cases.append({"case_id": row["case_id"], "target_law_id": law,
                      "target_type": "boundary_probe", "rationale": "Source-measured " + kind +
                      " access body position with statutory blocking unresolved.",
                      "variable_assignments": {"access_kind": variable("world_setup", kind,
                          "Fixed within access-kind pair"),
                          "parking_position": variable("controller", position,
                          "Only deliberate within-pair parking target change")},
                      "unresolved_judgment_calls": [phrase],
                      "paired_probe_id": kind + "_parking_position",
                      "deliberate_differences": ["parking_position"],
                      "probe": {"primary_variable": "parking_position",
                                "comparison_or_standard": "Original body footprint versus same access corridor; no numeric legal standard",
                                "target_value_or_branch": position},
                      "recording_description": description})
    sweep = {"sweep_id": "c229404-alley-blocking-position",
             "target_law_id": law,
             "judgment_refs": [{"phrase": phrase, "note": note}],
             "status": "incomplete",
             "rationale": "No frozen quantitative blocking range; the legal judgment is reserved for original-source review.",
             "missing_inputs": ["Independently reviewed qualifying alley and parcel access source records",
                                "Original vehicle/access geometry and physical camera review"]}
    cases_ref = write("cases.json", {"cell_id": cell, "actor": actor,
                                    "status": "draft", "cases": cases,
                                    "sweep_specs": [sweep], "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": plan["assignment_id"],
                                  "stages": {"relevance_batch": rel_batch_ref,
                                             "relevance": rel_ref,
                                             "template": template_ref,
                                             "judgment_observables": [judgment_ref],
                                             "bindings": binding_ref,
                                             "cases": cases_ref}})


if __name__ == "__main__":
    main()
