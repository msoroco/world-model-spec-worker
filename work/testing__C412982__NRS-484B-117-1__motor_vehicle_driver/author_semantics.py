"""Author the exact-law semantic proposal chain for local review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sidewalk_case import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = "NRS-484B-117-1"
CELL = "C412982"
ACTOR = "motor_vehicle_driver"
ASSIGNMENT = json.loads((Path("inputs") / AID / "assignment.json").read_text())
TEXT = ASSIGNMENT["law"]["text"]
RECORDING = json.loads((ROOT / "construction.json").read_text())["recording_description"]
PARAMETERS = (
    ("travel_region", "world_setup", "road or reviewed sidewalk area"),
    ("entrance_kind", "world_setup", "none, permanent driveway, temporary driveway, alley entrance"),
    ("vehicle_power", "world_setup", "combustion or solely electric"),
    ("designed_wheels", "world_setup", "three or four wheels from original design source"),
    ("operator_role", "world_setup", "ordinary, authorized emergency, authorized law officer in duty, security guard in duty"),
)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    folder = ROOT / "proposals"
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": TEXT,
                                    "applies_to": [ACTOR],
                                    "relevance_type": "direct sidewalk driving restriction",
                                    "confidence": "high",
                                    "notes": "Actual sidewalk, entrance, vehicle and duty facts require original sources."}],
                 "borderline_excluded": []}
    write(folder / "relevance.json", relevance)
    write(folder / "relevance_batch.json", relevance)
    template = {"template_id": LAW + "@" + ACTOR, "law_id": LAW,
                "actor": ACTOR, "quote": TEXT,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "Driver moves a vehicle upon or within a legally identified sidewalk area.",
                                             "numeric_conditions": []},
                              "obligation": {"description": TEXT, "type": "must_not",
                                             "numeric_conditions": []},
                              "exceptions": [
                                  {"description": "Permanent driveway entrance crossing", "source_clause": "except at a permanent or temporary driveway or alley entrance"},
                                  {"description": "Temporary driveway entrance crossing", "source_clause": "except at a permanent or temporary driveway or alley entrance"},
                                  {"description": "Alley entrance crossing", "source_clause": "except at a permanent or temporary driveway or alley entrance"},
                                  {"description": "Solely electric vehicle designed for three wheels operated as an authorized emergency vehicle", "source_clause": "As an authorized emergency vehicle;"},
                                  {"description": "Solely electric vehicle designed for three wheels operated by an authorized law enforcement employee in official duties", "source_clause": "By an officer or other authorized employee of a law enforcement agency, as that term is defined in NRS 239C.065, in the course of his or her official duties;"},
                                  {"description": "Solely electric vehicle designed for three wheels operated by a security guard in official duties", "source_clause": "By a security guard, as that term is defined in NRS 648.016, in the course of his or her official duties."}],
                              "timing": {"description": "Observe original movement, sidewalk and entrance occupancy, vehicle design and time-bounded operator duty.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": []},
                "parameter_refs": [{"name": name, "kind": kind,
                                    "range_or_domain": domain}
                                   for name, kind, domain in PARAMETERS]}
    write(folder / "template.json", template)
    bindings = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                "established_contexts": ["paved road", "travel", "sidewalk"],
                "law_refs": [{"template_id": LAW + "@" + ACTOR,
                              "binding_kind": "direct"}],
                "context_refs": [], "fixed_parameters": [],
                "variable_parameters": [{"name": name, "kind": kind,
                                         "range_or_domain": domain,
                                         "used_by_laws": [LAW]}
                                        for name, kind, domain in PARAMETERS]}
    write(folder / "bindings.json", bindings)
    cases = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
             "cases": [], "sweep_specs": []}
    cases["cases"].append({"case_id": AID + "__baseline",
                           "target_law_id": None, "target_type": "baseline",
                           "rationale": "Shared off-sidewalk travel reference; no separate recording selected.",
                           "variable_assignments": {"travel_region": {"kind": "world_setup", "value": "road"},
                                                    "entrance_kind": {"kind": "world_setup", "value": "none"},
                                                    "vehicle_power": {"kind": "world_setup", "value": "combustion"},
                                                    "designed_wheels": {"kind": "world_setup", "value": 4},
                                                    "operator_role": {"kind": "world_setup", "value": "ordinary"}},
                           "unresolved_judgment_calls": [],
                           "recording_description": RECORDING})
    for item in CASES:
        variables = {"travel_region": {"kind": "world_setup", "value": item.travel_region},
                     "entrance_kind": {"kind": "world_setup", "value": item.entrance_kind or "none"},
                     "vehicle_power": {"kind": "world_setup", "value": item.vehicle_power},
                     "designed_wheels": {"kind": "world_setup", "value": item.designed_wheels},
                     "operator_role": {"kind": "world_setup", "value": item.operator_role}}
        target_type = ("violating_attempt" if item.suffix == "ordinary_sidewalk_travel"
                       else "compliant_attempt" if item.suffix == "ordinary_road_travel"
                       else "boundary_probe")
        cases["cases"].append({"case_id": AID + "__" + item.suffix,
                               "target_law_id": LAW,
                               "target_type": target_type,
                               "rationale": "Controlled physical sidewalk/entrance and source-qualified subsection 2 contrast; no legal verdict inferred.",
                               "variable_assignments": variables,
                               "unresolved_judgment_calls": ["statutory sidewalk identity and pedestrian purpose",
                                                              "entrance geometry",
                                                              "vehicle design and operator duty source review"],
                               "recording_description": RECORDING,
                               "paired_probe_id": "sidewalk_entrance_and_subsection2",
                               "deliberate_differences": list(variables),
                               "probe": {"primary_variable": "travel_region" if item.suffix == "ordinary_road_travel" else
                                         "entrance_kind" if item.entrance_kind else
                                         "operator_role" if item.vehicle_power == "solely_electric" else "travel_region",
                                         "comparison_or_standard": "original source-bound controlled contrast",
                                         "target_value_or_branch": variables}})
    write(folder / "cases.json", cases)
    refs = {stage: {"path": "proposals/" + stage + ".json",
                    "sha256": hashlib.sha256((folder / (stage + ".json")).read_bytes()).hexdigest()}
            for stage in ("relevance_batch", "relevance", "template", "bindings", "cases")}
    refs["judgment_observables"] = []
    write(folder / "semantic-index.json",
          {"format": "worker-semantic-delivery", "assignment_id": AID,
           "stages": refs})


if __name__ == "__main__":
    main()
