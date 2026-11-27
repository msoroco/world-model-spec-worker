"""Author source-grounded signed roadway proposals for local review."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from signed_road import AID, CASES

HERE = Path(__file__).resolve().parent
LAW = "LVMC-11-40-180-B"
ACTOR = "cycle_or_scooter_operator"
TEXT = json.loads((HERE.parents[1] / "inputs" / AID / "assignment.json").read_text())["law"]["text"]
RECORDING = json.loads((HERE / "construction.json").read_text())["recording_description"]
PARAMETERS = (
    ("device_kind", "world_setup", "bicycle, electric bicycle, electric scooter"),
    ("operator_conduct", "controller", "riding or walking device"),
    ("surface", "world_setup", "reviewed Las Vegas roadway"),
    ("signed_extent", "world_setup", "within, before or outside source-reviewed sign bounds"),
    ("sign_state", "world_setup", "source-reviewed in-place or absent three-category restriction"),
    ("director_administration", "world_setup", "original Director order, two consultations and traffic-flow determination"),
    ("movement", "controller", "through signed segment or turn away before boundary"),
)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def main():
    folder = HERE / "proposals"
    relevance = {"cell_id": "C412927", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": TEXT,
                                    "applies_to": [ACTOR],
                                    "relevance_type": "conditional signed roadway restriction",
                                    "confidence": "low",
                                    "notes": "Roadway sign does not establish Director order, consultations or determination."}],
                 "borderline_excluded": []}
    put(folder / "relevance.json", relevance)
    put(folder / "relevance_batch.json", relevance)
    put(folder / "template.json", {
        "template_id": LAW + "@" + ACTOR, "law_id": LAW,
        "actor": ACTOR, "quote": TEXT,
        "structure": {"law_id": LAW,
                      "activation": {"condition": "Director's source-reviewed order, City Traffic Engineer and Las Vegas Metropolitan Police Department consultations, traffic-flow determination, and in-place sign governing the actual Las Vegas roadway.",
                                     "numeric_conditions": []},
                      "obligation": {"description": "A person must not disobey the in-place sign's actual riding prohibition for bicycles, electric bicycles or electric scooters on its governed roadway.",
                                     "type": "must_not", "numeric_conditions": []},
                      "exceptions": [],
                      "timing": {"description": "Join sign presence, covered riding and original roadway positions during governed travel.",
                                 "numeric_conditions": []},
                      "judgment_calls_needed": []},
        "parameter_refs": [{"name": n, "kind": k, "range_or_domain": d}
                           for n, k, d in PARAMETERS]})
    put(folder / "bindings.json", {
        "cell_id": "C412927", "actor": ACTOR, "status": "draft",
        "established_contexts": [
            "paved road and travel in the frozen cell",
            "City roadway, Director order, City Traffic Engineer and LVMPD consultations,",
            "Director determination, sign posting and governed extent must be joined from the original source packet before physical execution"],
        "law_refs": [{"template_id": LAW + "@" + ACTOR,
                      "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [],
        "variable_parameters": [{"name": n, "kind": k, "range_or_domain": d,
                                 "used_by_laws": [LAW]} for n, k, d in PARAMETERS]})
    cases = {"cell_id": "C412927", "actor": ACTOR,
             "status": "draft", "cases": [], "sweep_specs": []}
    cases["cases"].append({
        "case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline",
        "rationale": "Shared roadway reference; no separate baseline recording selected.",
        "variable_assignments": {
            "device_kind": {"kind": "world_setup", "value": "bicycle"},
            "operator_conduct": {"kind": "controller", "value": "riding"},
            "surface": {"kind": "world_setup", "value": "roadway"},
            "signed_extent": {"kind": "world_setup", "value": "within"},
            "sign_state": {"kind": "world_setup", "value": "posted"},
            "director_administration": {"kind": "world_setup", "value": "source-reviewed"},
            "movement": {"kind": "controller", "value": "through"}},
        "unresolved_judgment_calls": [],
        "recording_description": RECORDING})
    for case in CASES:
        variables = {"device_kind": {"kind": "world_setup", "value": case.device_kind},
                     "operator_conduct": {"kind": "controller", "value": case.conduct},
                     "surface": {"kind": "world_setup", "value": "roadway"},
                     "signed_extent": {"kind": "world_setup", "value": case.extent},
                     "sign_state": {"kind": "world_setup", "value": case.sign_state},
                     "director_administration": {"kind": "world_setup", "value": "source-reviewed"},
                     "movement": {"kind": "controller", "value": case.movement}}
        target = ("violating_attempt" if case.suffix == "bicycle_disobey"
                  else "compliant_attempt" if case.suffix in
                  ("bicycle_obey", "bicycle_walking")
                  else "boundary_probe")
        cases["cases"].append({"case_id": AID + "__" + case.suffix,
                               "target_law_id": LAW, "target_type": target,
                               "rationale": "Original source-grounded device, conduct, signed extent, administrative record and movement comparison; no legal verdict inferred.",
                               "variable_assignments": variables,
                               "unresolved_judgment_calls": ["Director's traffic-flow assessment is an external source record; legal consequence remains unasserted"],
                               "recording_description": RECORDING,
                               "paired_probe_id": "signed_roadway_branch_comparisons",
                               "deliberate_differences": list(variables),
                               "probe": {"primary_variable": "signed_extent",
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
