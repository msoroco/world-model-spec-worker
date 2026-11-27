"""Author source-grounded City sidewalk semantic proposals for local review."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from sidewalk_030 import AID, CASES, LAW

HERE = Path(__file__).resolve().parent
ACTOR = "motorcycle_or_moped_operator"
TEXT = json.loads((HERE.parents[1] / "inputs" / AID / "assignment.json").read_text())["law"]["text"]
RECORDING = json.loads((HERE / "construction.json").read_text())["recording_description"]
PARAMETERS = (("device_kind", "world_setup", "source-qualified motorcycle or motor scooter"),
              ("operator_conduct", "controller", "mounted riding or walking"),
              ("surface", "world_setup", "pedestrian sidewalk or adjacent road"),
              ("side", "world_setup", "north or south reviewed sidewalk"),
              ("municipality", "world_setup", "Las Vegas City or surveyed outside boundary"))


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    folder = HERE / "proposals"
    relevance = {"cell_id": "C412982", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": TEXT,
                                    "applies_to": [ACTOR],
                                    "relevance_type": "specific_match",
                                    "confidence": "high",
                                    "notes": "Municipal boundary, device class and mounted riding need original source review."}],
                 "borderline_excluded": []}
    put(folder / "relevance.json", relevance)
    put(folder / "relevance_batch.json", relevance)
    put(folder / "template.json", {
        "template_id": LAW + "@" + ACTOR, "law_id": LAW, "actor": ACTOR, "quote": TEXT,
        "structure": {"law_id": LAW,
                      "activation": {"condition": "A source-qualified motorcycle or motor scooter is operated within the City on a road with an adjacent pedestrian-use sidewalk.",
                                     "numeric_conditions": []},
                      "obligation": {"description": "No motorcycle or motor scooter shall be ridden upon any sidewalk of the City.",
                                     "type": "must_not", "numeric_conditions": []},
                      "exceptions": [],
                      "timing": {"description": "Observe original device, mounted conduct, sidewalk occupation and City location throughout travel.",
                                 "numeric_conditions": []},
                      "judgment_calls_needed": []},
        "parameter_refs": [{"name": n, "kind": k, "range_or_domain": d}
                           for n, k, d in PARAMETERS]})
    put(folder / "bindings.json", {
        "cell_id": "C412982", "actor": ACTOR, "status": "draft",
        "established_contexts": ["paved road", "travel", "sidewalk"],
        "law_refs": [{"template_id": LAW + "@" + ACTOR, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": n, "kind": k, "range_or_domain": d,
                                 "used_by_laws": [LAW]} for n, k, d in PARAMETERS]})
    cases = {"cell_id": "C412982", "actor": ACTOR, "status": "draft",
             "cases": [], "sweep_specs": []}
    baseline = CASES[3]
    variables = {"device_kind": {"kind": "world_setup", "value": baseline.device_kind},
                 "operator_conduct": {"kind": "controller", "value": baseline.conduct},
                 "surface": {"kind": "world_setup", "value": baseline.surface},
                 "side": {"kind": "world_setup", "value": baseline.side},
                 "municipality": {"kind": "world_setup", "value": baseline.municipality}}
    cases["cases"].append({"case_id": AID + "__baseline", "target_law_id": None,
                           "target_type": "baseline", "rationale": "Adjacent-road reference; no baseline recording selected.",
                           "variable_assignments": variables, "unresolved_judgment_calls": [],
                           "recording_description": RECORDING})
    for case in CASES:
        variables = {"device_kind": {"kind": "world_setup", "value": case.device_kind},
                     "operator_conduct": {"kind": "controller", "value": case.conduct},
                     "surface": {"kind": "world_setup", "value": case.surface},
                     "side": {"kind": "world_setup", "value": case.side},
                     "municipality": {"kind": "world_setup", "value": case.municipality}}
        target = ("violating_attempt" if case.suffix == "motorcycle_riding_sidewalk_north"
                  else "compliant_attempt" if case.suffix in
                  ("motorcycle_walking_sidewalk", "motorcycle_riding_road")
                  else "boundary_probe")
        cases["cases"].append({"case_id": AID + "__" + case.suffix,
                               "target_law_id": LAW, "target_type": target,
                               "rationale": "Original source-grounded device, mounted conduct, surface and municipal comparison; no legal verdict inferred.",
                               "variable_assignments": variables,
                               "unresolved_judgment_calls": ["municipal boundary and device qualification"],
                               "recording_description": RECORDING,
                               "paired_probe_id": "city_sidewalk_branch_comparisons",
                               "deliberate_differences": list(variables),
                               "probe": {"primary_variable": "surface",
                                         "comparison_or_standard": "reviewed original physical contrast",
                                         "target_value_or_branch": variables}})
    put(folder / "cases.json", cases)
    stages = {stage: {"path": "proposals/" + stage + ".json",
                      "sha256": sha256((folder / (stage + ".json")).read_bytes()).hexdigest()}
              for stage in ("relevance_batch", "relevance", "template", "bindings", "cases")}
    stages["judgment_observables"] = []
    put(folder / "semantic-index.json",
        {"format": "worker-semantic-delivery", "assignment_id": AID,
         "stages": stages})


if __name__ == "__main__":
    main()
