"""Draft canonical stage proposals for the exact C158208 nearest-view pair.

The proposals preserve statutory uncertainty and do not adopt any local job.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
LAW = "NRS-484B-257-1"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
KINDS = ("nearest_view_response", "nearest_view_uninterrupted")


def recording_description() -> dict:
    channels = [
        ("ego_body_and_speed", "Original ego bounding-box vertices and velocity"),
        ("through_vehicle_body_and_occupancy", "Original through body and intersection overlap"),
        ("nearest_view_raycast", "Original Native raycast and first view"),
        ("camera_pixels", "Four synchronized original camera images"),
    ]
    return {"channels": [{"name": name, "unit": "structured",
             "method": method + " sealed to the original world tick",
             "time_window": "all 900 original world ticks",
             "reference_frame": "reviewed C158208 CARLA world frame",
             "sampling_rate_hz": 20,
             "uncertainty": "realized motion and visibility await original capture review"}
             for name, method in channels],
            "context_inputs": [{"name": "reviewed_site", "unit": "structured",
                                "method": "eight source-hashed original C158208 surveys and loaded OpenDRIVE"},
                               {"name": "governing_control", "unit": "structured",
                                "method": "reviewed sign and exclusion of officer or signal control"}],
            "limitations": ["Diagnostic fixtures do not establish actual motion, sign visibility or legal right of way."]}


JUDGMENTS = [
    ("proper signs have been erected", "Governing sign identity and physical placement need independent review.",
     "governing_control"),
    ("point nearest the intersection where the driver has a view of approaching traffic on the through highway",
     "Nearest available view depends on original geometry, road users and raycasts.", "nearest_view_raycast"),
    ("approaching so closely on such through highway as to constitute an immediate hazard",
     "Immediate hazard is a legal judgment over original through-vehicle history.",
     "through_vehicle_body_and_occupancy"),
    ("yield the right-of-way", "Priority remains unresolved from a controller label.",
     "ego_body_and_speed"),
]


def _write(directory: Path, name: str, value: dict) -> dict:
    path = directory / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build() -> dict:
    assignment = json.loads((ROOT / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    quote = assignment["law"]["text"]
    directory = HERE / "proposals"
    directory.mkdir(exist_ok=True)
    relevance = {"status": "draft", "cell_id": "C158208", "actor": ACTOR,
                 "relevant_laws": [{"law_id": LAW, "quote": quote,
                                    "applies_to": [ACTOR], "confidence": "low",
                                    "relevance_type": "yield-sign nearest-view branch",
                                    "notes": "Original sign, site and through traffic still need source review."}],
                 "borderline_excluded": []}
    references = {"relevance_batch": _write(directory, "relevance_batch.json", relevance),
                  "relevance": _write(directory, "relevance.json", relevance)}
    parameters = [
        {"name": "response_mode", "kind": "controller",
         "range_or_domain": "observed-conflict response or uninterrupted engineering controller"},
        {"name": "reviewed_site", "kind": "world_setup",
         "range_or_domain": "single reviewed C158208 nearest-view site"},
        {"name": "through_traffic", "kind": "world_setup",
         "range_or_domain": "source-reviewed through-highway actor route and schedule"},
        {"name": "capture_profile", "kind": "world_setup",
         "range_or_domain": "four original camera streams, 20 Hz, 900 frames"},
    ]
    template = {"status": "draft", "law_id": LAW, "actor": ACTOR,
                "template_id": TEMPLATE, "quote": quote,
                "structure": {"activation": {"condition": "Driver approaches a properly signed yield intersection without officer or signal control.",
                                             "numeric_conditions": []},
                              "obligation": {"type": "yield", "description": "Slow or stop at the applicable reference and yield to protected through-highway vehicles during crossing.",
                                             "numeric_conditions": []},
                              "exceptions": [{"source_clause": "Except when traffic is being controlled by a police officer or a traffic-control signal",
                                              "trigger": "officer or signal control",
                                              "effect": "this signed-intersection rule does not govern",
                                              "description": "Independently verify actual governing control."}],
                              "timing": {"description": "Original approach, first view and full across-or-within intersection history.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                                         for phrase, note, _ in JUDGMENTS]},
                "parameter_refs": parameters}
    references["template"] = _write(directory, "template.json", template)
    refs = []
    for index, (phrase, note, observable) in enumerate(JUDGMENTS, 1):
        context = observable in ("governing_control",)
        requirement = {"name": observable, "unit": "structured",
                       "description": "Original source-bound observations for " + phrase + "."}
        proposal = {"status": "draft", "template_id": TEMPLATE, "phrase": phrase,
                    "note": note,
                    "observable_requirements": {
                        "observables": [{"name": "ego_body_and_speed", "unit": "structured",
                                         "description": "Retained original ego body and velocity history."}],
                        "context_inputs": [requirement] if context else [],
                        "sweep_dimensions": [], "landmarks": [],
                        "recording_needs": [requirement] if not context else
                            [{"name": "ego_body_and_speed", "unit": "structured",
                              "description": "Original ego response history."}],
                        "limitations": ["Original observations do not decide statutory applicability or priority."]}}
        refs.append(_write(directory, f"judgment-{index}.json", proposal))
    references["judgment_observables"] = refs
    binding = {"status": "draft", "cell_id": "C158208", "actor": ACTOR,
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "context_refs": [],
               "established_contexts": ["Frozen yield-sign intersection identity; original site remains source-gated."],
               "fixed_parameters": [{"name": "assigned_cell", "value": "C158208",
                                     "rationale": "Frozen catalog identity, not a reviewed physical site."}],
               "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in parameters]}
    references["bindings"] = _write(directory, "bindings.json", binding)
    description = recording_description()
    unresolved = [item[0] for item in JUDGMENTS]
    base = {item["name"]: {"kind": item["kind"], "value": {
        "response_mode": "response", "reviewed_site": "source-reviewed C158208 site",
        "through_traffic": "fixed original through-highway route and schedule",
        "capture_profile": "four original camera streams, 20 Hz, 900 frames"}[item["name"]]}
        for item in parameters}
    cases = [{"case_id": ASSIGNMENT + "__semantic_baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Shared source-dependent setup reference; no separate recording.",
              "recording_description": description, "unresolved_judgment_calls": unresolved,
              "variable_assignments": base}]
    for kind in KINDS:
        assignments = json.loads(json.dumps(base))
        assignments["response_mode"]["value"] = "response" if kind.endswith("response") else "uninterrupted"
        cases.append({"case_id": ASSIGNMENT + "__" + kind, "target_law_id": LAW,
                      "target_type": "boundary_probe", "paired_probe_id": "yield_nearest_view",
                      "deliberate_differences": ["response_mode"],
                      "probe": {"primary_variable": "response_mode",
                                "comparison_or_standard": "yield_nearest_view",
                                "target_value_or_branch": kind},
                      "rationale": "Source-bound comparison of realized response near the reviewed first view.",
                      "recording_description": description,
                      "unresolved_judgment_calls": unresolved,
                      "variable_assignments": assignments})
    sweeps = [{"sweep_id": f"pending-{index}", "target_law_id": LAW,
               "judgment_refs": [{"phrase": phrase, "note": note}],
               "status": "incomplete",
               "missing_inputs": ["Reviewed original site and feasible source-grounded physical range"],
               "rationale": "No engineering range is treated as a legal cutoff."}
              for index, (phrase, note, _) in enumerate(JUDGMENTS, 1)]
    references["cases"] = _write(directory, "cases.json",
                                 {"status": "draft", "cell_id": "C158208", "actor": ACTOR,
                                  "cases": cases, "sweep_specs": sweeps,
                                  "sweeps_expanded": False})
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
             "stages": references}
    (directory / "semantic-index.json").write_text(json.dumps(index, indent=2) + "\n")
    return {"stage_count": 9, "selected_cases": 2}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
