"""Build source-grounded canonical-stage proposals for exact C378707 law."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())
ASSIGNMENT = PLAN["assignment_id"]
LAW = "NRS-484B-477-1a"
CELL = "C378707"
ACTOR = "motor_vehicle_driver"
QUOTE = PLAN["law_text"]
TEMPLATE = LAW + "@" + ACTOR


def _write(folder, name, data):
    path = folder / (name + ".json")
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
    return {"path": "proposals/" + path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _description():
    channels = []
    for observation in PLAN["observations"]:
        channels.append({
            "name": observation["name"], "method": observation["source"],
            "unit": "structured original source", "sampling_rate_hz": 20,
            "reference_frame": "source-surveyed business alley and original Native frame map",
            "time_window": "all 900 original Native frames",
            "uncertainty": "statutory activity, expeditiousness and ordinance review pending",
        })
    return {"channels": channels,
            "context_inputs": [{"name": "reviewed_business_alley_packet", "unit": "source",
                                "method": "source-hashed alley, frontage, jurisdiction, ordinance and actual Native readback"}],
            "limitations": ["Requested passenger or goods schedule is not observed original activity.",
                            "A diagnostic fixture does not establish stop, stand, park, expeditiousness or ordinance applicability."]}


def build():
    folder = ROOT / "proposals"
    folder.mkdir(exist_ok=True)
    relevance = {"status": "draft", "cell_id": CELL, "actor": ACTOR,
                 "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
                                    "applies_to": [ACTOR], "confidence": "medium",
                                    "relevance_type": "motor vehicle loading in source-qualified business-district alley",
                                    "notes": "Passenger loading, goods exception and local ordinance require original source review."}],
                 "borderline_excluded": []}
    references = {"relevance": _write(folder, "relevance", relevance),
                  "relevance_batch": _write(folder, "relevance_batch", relevance)}
    judgments = [
        ("within an alley in a business district",
         "Source-reviewed alley, public use, frontage, business uses and local jurisdiction are required."),
        ("Stop, stand or park",
         "Original vehicle, driver and traffic histories distinguish the alternatives; no duration surrogate is asserted."),
        ("expeditious loading or unloading of goods",
         "Actual goods contact and idle intervals are measured; expeditiousness remains a legal judgment."),
        ("Unless otherwise provided by ordinance",
         "Effective text, issuing authority, jurisdiction and applicability require independent review."),
    ]
    parameters = [
        {"name": "alley_classification", "kind": "world_setup",
         "range_or_domain": "source-reviewed business-district alley"},
        {"name": "loading_activity", "kind": "controller",
         "range_or_domain": "passenger boarding or goods handling from original actor contact"},
        {"name": "vehicle_halt", "kind": "controller",
         "range_or_domain": "original approach, halt, hold and departure"},
        {"name": "driver_presence", "kind": "world_setup",
         "range_or_domain": "original driver in vehicle or outside"},
        {"name": "ordinance_status", "kind": "world_setup",
         "range_or_domain": "reviewed no applicable override or reviewed authorization"},
    ]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
                "quote": QUOTE, "parameter_refs": parameters,
                "structure": {
                    "law_id": LAW,
                    "activation": {"condition": "A responsible person stops, stands or parks a motor vehicle within a source-qualified business-district alley.",
                                   "numeric_conditions": []},
                    "obligation": {"type": "must_not",
                                   "description": "Do not stop, stand or park in the covered alley unless an exception or applicable local ordinance provides otherwise.",
                                   "numeric_conditions": []},
                    "exceptions": [
                        {"source_clause": "except for the expeditious loading or unloading of goods",
                         "description": "Source-proven actual expeditious goods loading or unloading."},
                        {"source_clause": "Unless otherwise provided by ordinance of the local authority having jurisdiction",
                         "description": "Source-reviewed effective and applicable local ordinance otherwise provides."},
                    ],
                    "timing": {"description": "Measure original actor contact, driver presence, halt and idle intervals across the 45-second capture.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                              for phrase, note in judgments],
                }}
    references["template"] = _write(folder, "template", template)
    observation_names = [entry["name"] for entry in PLAN["observations"]]
    judgment_refs = []
    for index, (phrase, note) in enumerate(judgments, 1):
        requirements = {"context_inputs": [{"name": "reviewed_business_alley_packet", "unit": "source",
                                              "description": "Original source-hashed alley, frontage, actor and jurisdiction review."}],
                        "landmarks": [], "observables": [
                            {"name": name, "unit": "structured original source",
                             "description": "Original sealed 20 Hz source for " + name.replace("_", " ")}
                            for name in observation_names],
                        "recording_needs": [{"name": "four_original_camera_streams",
                                             "unit": "structured original source",
                                             "description": "Four synchronized original Native camera streams."}],
                        "sweep_dimensions": [],
                        "limitations": ["Original source review and legal interpretation are pending; no legal cutoff is inferred from a fixture."]}
        judgment_refs.append(_write(folder, "judgment-" + str(index),
                                    {"status": "draft", "template_id": TEMPLATE,
                                     "phrase": phrase, "note": note,
                                     "observable_requirements": requirements}))
    references["judgment_observables"] = judgment_refs
    binding = {"status": "draft", "cell_id": CELL, "actor": ACTOR,
               "context_refs": [],
               "established_contexts": ["Frozen C378707 business-district alley loading task; exact surveyed site pending."],
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "fixed_parameters": [{"name": "reviewed_business_alley_packet",
                                     "value": "source_packet_pending",
                                     "rationale": "Hold original alley, vehicle, actor zones, cadence and four views fixed."}],
               "variable_parameters": [dict(row, used_by_laws=[LAW]) for row in parameters]}
    references["bindings"] = _write(folder, "bindings", binding)
    description = _description()
    case_rows = []
    variant_values = {
        "passenger_active_stop": ("passenger_active", "halt", "in_vehicle", "no_override"),
        "passenger_wait_stand": ("passenger_wait_then_board", "hold", "in_vehicle", "no_override"),
        "passenger_driver_exit_park": ("passenger_active", "halt", "outside_vehicle", "no_override"),
        "goods_active_load": ("goods_continuous", "halt", "in_vehicle", "no_override"),
        "goods_wait_interrupted": ("goods_interrupted", "halt", "in_vehicle", "no_override"),
        "ordinance_passenger_authorized": ("passenger_active", "halt", "in_vehicle", "reviewed_authorization"),
    }
    for row in PLAN["cases"]:
        variant = row["variant"]
        activity, halt, driver, ordinance = variant_values[variant]
        values = {"alley_classification": "source_reviewed_business_district_alley",
                  "loading_activity": activity, "vehicle_halt": halt,
                  "driver_presence": driver, "ordinance_status": ordinance}
        assignments = {p["name"]: {"kind": p["kind"], "value": values[p["name"]]}
                       for p in parameters}
        case_rows.append({"case_id": row["case_id"], "target_law_id": LAW,
                          "target_type": "boundary_probe", "paired_probe_id": variant,
                          "rationale": row["target_description"],
                          "deliberate_differences": [row["deliberate_condition"]],
                          "recording_description": description,
                          "variable_assignments": assignments,
                          "unresolved_judgment_calls": [phrase for phrase, _ in judgments],
                          "probe": {"primary_variable": "loading_activity",
                                    "target_value_or_branch": variant,
                                    "comparison_or_standard": "other exact business-alley variants"}})
    baseline = dict(case_rows[0])
    baseline.update({"case_id": ASSIGNMENT + "__baseline", "target_type": "baseline",
                     "paired_probe_id": "baseline",
                     "rationale": "Shared reviewed alley, motor vehicle and capture reference; baseline is not dispatched."})
    cases = {"status": "draft", "cell_id": CELL, "actor": ACTOR,
             "cases": [baseline] + case_rows, "sweeps_expanded": True,
             "sweep_specs": [{"sweep_id": "legal_phrase_" + str(i),
                              "target_law_id": LAW, "status": "incomplete",
                              "judgment_refs": [{"phrase": phrase, "note": note}],
                              "rationale": "No accepted original measurement or training judgment range for this phrase is supplied.",
                              "missing_inputs": ["Original source review and physical judgment range."]}
                             for i, (phrase, note) in enumerate(judgments, 1)]}
    references["cases"] = _write(folder, "cases", cases)
    _write(folder, "semantic-index", {"format": "worker-semantic-delivery",
                                      "assignment_id": ASSIGNMENT,
                                      "source": "Exact NRS 484B.477(1)(a), frozen C378707 cell and original witness",
                                      "status": "draft", "stages": references})


if __name__ == "__main__":
    build()
