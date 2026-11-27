"""Author source-grounded Fremont semantic proposals for local review."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from fremont_180 import AID, CASES

HERE = Path(__file__).resolve().parent
LAW = "LVMC-11-40-180-A"
ACTOR = "cycle_or_scooter_operator"
TEXT = json.loads((HERE.parents[1] / "inputs" / AID / "assignment.json").read_text())["law"]["text"]
RECORDING = json.loads((HERE / "construction.json").read_text())["recording_description"]
PARAMETERS = (
    ("device_kind", "world_setup", "bicycle, electric bicycle, electric scooter"),
    ("operator_conduct", "controller", "riding or walking device"),
    ("surface", "world_setup", "reviewed north or south sidewalk, adjacent road"),
    ("side", "world_setup", "north or south reviewed sidewalk"),
    ("municipal_extent", "world_setup", "before Main, between Main and Seventh, after Seventh"),
    ("sign_state", "world_setup", "source reviewed posted or absent three-category signs"),
)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def main():
    folder = HERE / "proposals"
    relevance = {"cell_id": "C412982", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": TEXT,
                                    "applies_to": [ACTOR],
                                    "relevance_type": "direct named sidewalk riding prohibition",
                                    "confidence": "high",
                                    "notes": "Fremont Main-to-Seventh map and signs need original review."}],
                 "borderline_excluded": []}
    put(folder / "relevance.json", relevance)
    put(folder / "relevance_batch.json", relevance)
    put(folder / "template.json", {
        "template_id": LAW + "@" + ACTOR, "law_id": LAW,
        "actor": ACTOR, "quote": TEXT,
        "structure": {"law_id": LAW,
                      "activation": {"condition": "Person rides a named covered device on an actual sidewalk on Fremont Street strictly between Main and Seventh Streets.",
                                     "numeric_conditions": []},
                      "obligation": {"description": "Rider sidewalk prohibition; separate area sign posting sentence.",
                                     "type": "must_not", "numeric_conditions": []},
                      "exceptions": [],
                      "timing": {"description": "Observe original conduct, device, sidewalk surface and municipal longitudinal extent throughout travel.",
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
    cases = {"cell_id": "C412982", "actor": ACTOR,
             "status": "draft", "cases": [], "sweep_specs": []}
    cases["cases"].append({
        "case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline",
        "rationale": "Shared adjacent-road reference; no baseline recording selected.",
        "variable_assignments": {
            "device_kind": {"kind": "world_setup", "value": "bicycle"},
            "operator_conduct": {"kind": "controller", "value": "riding"},
            "surface": {"kind": "world_setup", "value": "road"},
            "side": {"kind": "world_setup", "value": "north"},
            "municipal_extent": {"kind": "world_setup", "value": "between"},
            "sign_state": {"kind": "world_setup", "value": "posted"}},
        "unresolved_judgment_calls": [],
        "recording_description": RECORDING})
    for case in CASES:
        variables = {"device_kind": {"kind": "world_setup", "value": case.device_kind},
                     "operator_conduct": {"kind": "controller", "value": case.conduct},
                     "surface": {"kind": "world_setup", "value": case.surface},
                     "side": {"kind": "world_setup", "value": case.side},
                     "municipal_extent": {"kind": "world_setup", "value": case.extent},
                     "sign_state": {"kind": "world_setup", "value": case.sign_state}}
        target = ("violating_attempt" if case.suffix == "bicycle_riding_north"
                  else "compliant_attempt" if case.suffix in
                  ("bicycle_walking_north", "bicycle_riding_road")
                  else "boundary_probe")
        cases["cases"].append({"case_id": AID + "__" + case.suffix,
                               "target_law_id": LAW, "target_type": target,
                               "rationale": "Original source-grounded device, conduct, municipal extent and sign comparison; no legal verdict inferred.",
                               "variable_assignments": variables,
                               "unresolved_judgment_calls": ["municipal map identity",
                                                              "sign coverage and legal consequence"],
                               "recording_description": RECORDING,
                               "paired_probe_id": "fremont_sidewalk_branch_comparisons",
                               "deliberate_differences": list(variables),
                               "probe": {"primary_variable": "municipal_extent",
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
