"""Author canonical source-grounded protected-lane semantic proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from author_bundles import RECORDING

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = "NRS-486-341"
CELL = "C147339"
ACTOR = "motor_vehicle_driver"
TEXT = ("Every motorcycle or moped when being driven on the highway is entitled to full "
        "use of the traffic lane it is occupying, and a person shall not drive another "
        "motor vehicle in a manner which would deprive any such motorcycle or moped of such use.")
PARAMETERS = (("protected_kind", "world_setup", "motorcycle or moped"),
              ("ego_path", "controller", "adjacent, edge or deep"),
              ("protected_driven", "world_setup", "true or false"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    p = ROOT / "proposals"
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": TEXT, "applies_to": [ACTOR],
                                    "relevance_type": "specific_match", "confidence": "high",
                                    "notes": "Original motorcycle or moped motion, public highway, occupied lane and possible deprivation remain source-gated."}],
                 "borderline_excluded": []}
    write(p / "relevance.json", relevance)
    write(p / "relevance_batch.json", relevance)
    template = {"template_id": LAW + "@" + ACTOR, "law_id": LAW, "actor": ACTOR,
                "quote": TEXT,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "A motorcycle or moped is being driven on a highway in an occupied traffic lane while another motor vehicle is driven nearby.",
                                             "numeric_conditions": []},
                              "obligation": {"description": "The other motor vehicle must not be driven in a manner which would deprive the motorcycle or moped of full use of its occupied lane.",
                                             "type": "must_not", "numeric_conditions": []},
                              "exceptions": [],
                              "timing": {"description": "During the original driven protected-vehicle and other-motor-vehicle encounter.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": []},
                "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                                   for name, kind, domain in PARAMETERS]}
    write(p / "template.json", template)
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "established_contexts": ["one-way multilane road", "motorcycle or moped protected occupant",
                                        "distinct nearby motor-vehicle lane"],
               "law_refs": [{"template_id": LAW + "@" + ACTOR, "binding_kind": "direct"}],
               "context_refs": [],
               "fixed_parameters": [],
               "variable_parameters": [{"name": name, "kind": kind,
                                        "range_or_domain": domain, "used_by_laws": [LAW]}
                                       for name, kind, domain in PARAMETERS]}
    write(p / "bindings.json", binding)
    cases = {"cell_id": CELL, "actor": ACTOR, "status": "draft", "cases": [], "sweep_specs": []}
    baseline_params = plan["cases"][0]
    cases["cases"].append({"case_id": AID + "__baseline", "target_law_id": None,
                           "target_type": "baseline", "rationale": "Reference adjacent-lane route; no separate recording.",
                           "variable_assignments": {name: {"kind": kind, "value": baseline_params[name]}
                                                    for name, kind, _ in PARAMETERS},
                           "unresolved_judgment_calls": [], "recording_description": RECORDING})
    for item in plan["cases"]:
        suffix = item["case_id"].split("__")[-1]
        variables = {name: {"kind": kind, "value": item[name]} for name, kind, _ in PARAMETERS}
        cases["cases"].append({"case_id": item["case_id"], "target_law_id": LAW,
                               "target_type": "compliant_attempt" if suffix in
                               ("motorcycle_adjacent_clear", "motorcycle_stationary_edge") else
                               "violating_attempt",
                               "rationale": "Original lane, participant class and protected motion contrasts; target type is an authored probe, not a legal verdict.",
                               "variable_assignments": variables,
                               "unresolved_judgment_calls": ["full use of occupied lane",
                                                             "would deprive"],
                               "recording_description": RECORDING,
                               "paired_probe_id": "protected_lane_use",
                               "deliberate_differences": list(variables),
                               "probe": {"primary_variable": "ego_path",
                                         "comparison_or_standard": "original source-bound controlled contrast",
                                         "target_value_or_branch": suffix}})
    write(p / "cases.json", cases)
    refs = {stage: {"path": "proposals/" + stage + ".json",
                    "sha256": hashlib.sha256((p / (stage + ".json")).read_bytes()).hexdigest()}
            for stage in ("relevance_batch", "relevance", "template", "bindings", "cases")}
    refs["judgment_observables"] = []
    write(p / "semantic-index.json", {"format": "worker-semantic-delivery",
                                      "assignment_id": AID, "stages": refs})


if __name__ == "__main__":
    main()
