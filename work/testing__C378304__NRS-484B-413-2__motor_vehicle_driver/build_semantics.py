"""Draft canonical semantic stages for the five selected signal probes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN = json.loads((ROOT / "case-plan.json").read_text())
OUT = ROOT / "proposals"
OUT.mkdir(exist_ok=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(name: str, value: dict) -> dict:
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return {"path": "proposals/" + name, "sha256": sha(path)}


def main() -> None:
    aid, law, cell, actor = (PLAN[key] for key in ("assignment_id", "law_id", "cell_id", "actor"))
    quote = PLAN["law_text"]
    relevance = dump("relevance.json", {"cell_id": cell, "actor": actor, "status": "draft",
        "relevant_laws": [{"law_id": law, "quote": quote, "applies_to": [actor],
            "relevance_type": "source-gated business-district highway right turn",
            "confidence": "medium", "notes": "Highway and district frontage/building use require original local source review."}],
        "borderline_excluded": []})
    variables = {"signal_start_distance_ft": "controller", "signal_continuity_request": "controller",
                 "weather_request": "world_setup"}
    refs = [{"name": name, "kind": kind, "range_or_domain": "exact selected target or reviewed site"}
            for name, kind in variables.items()]
    template = dump("template.json", {"template_id": law + "@" + actor,
        "law_id": law, "actor": actor, "status": "draft", "quote": quote,
        "structure": {"law_id": law,
            "activation": {"condition": "A motor-vehicle driver intends to turn from a direct course on a highway.",
                           "numeric_conditions": []},
            "obligation": {"description": "Give a continuous turn signal over the applicable last traveled distance before changing course.",
                           "type": "must", "numeric_conditions": [
                               {"value": 100, "unit": "ft", "comparison": "not_less_than",
                                "context": "business or residential district"},
                               {"value": 300, "unit": "ft", "comparison": "not_less_than",
                                "context": "any other area"}]},
            "exceptions": [],
            "timing": {"description": "Continuous during the applicable last traveled feet prior to changing course, regardless of weather.",
                       "numeric_conditions": []},
            "judgment_calls_needed": []}, "parameter_refs": refs})
    bindings = dump("bindings.json", {"cell_id": cell, "actor": actor, "status": "draft",
        "established_contexts": ["The cell selects a business-district right-turn signaling probe; physical district and highway status require reviewed source packets."],
        "law_refs": [{"template_id": law + "@" + actor, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "district_kind", "kind": "world_setup", "value": "business",
                              "source": "frozen C378304 selected branch"},
                             {"name": "maneuver", "kind": "world_setup", "value": "right_turn",
                              "source": "frozen C378304 selected branch"}],
        "variable_parameters": [dict(item, used_by_laws=[law]) for item in refs]})
    channel_specs = (
        ("native_frame", "frame", "original CARLA tick identity"),
        ("ego_xy", "m", "original ego transform position readback"),
        ("right_signal", "boolean", "original vehicle light-state readback"),
        ("course_change", "boolean", "original ego heading against reviewed approach"),
        ("weather", "categorical", "original Native weather readback"),
        ("four_camera_frames", "native pixels", "four synchronized original camera sources"),
    )
    normalized = {"channels": [{"name": name, "unit": unit, "method": method,
                                 "sampling_rate_hz": 20,
                                 "time_window": "full 900-frame, 45-second attempt",
                                 "reference_frame": "original CARLA world and frame identity",
                                 "uncertainty": "one retained 20 Hz sample"}
                                for name, unit, method in channel_specs],
                  "context_inputs": [{"name": name, "unit": "source record", "method": "SHA-bound local review packet"}
                                     for name in ("highway", "business_district_frontage_and_use",
                                                  "freight_loading_zone", "driver_and_vehicle")],
                  "limitations": ["Controller target is not the observed signaling distance.",
                                  "Original district and highway facts require independent review."]}
    description = {case["case_id"]: normalized for case in PLAN["cases"]}
    cases = [{"case_id": aid + "__baseline", "target_law_id": None, "target_type": "baseline",
              "rationale": "Nonexecuted neutral reference for the linked signal probes.",
              "variable_assignments": {name: {"kind": kind, "value": "unselected"}
                                       for name, kind in variables.items()},
              "unresolved_judgment_calls": [],
              "recording_description": next(iter(description.values()))}]
    for row in PLAN["cases"]:
        tag = row["case_id"].rsplit("__", 1)[-1]
        target_type = ("violating_attempt" if tag in ("short80", "interrupted") else
                       "compliant_attempt" if tag == "continuous100" else "boundary_probe")
        values = row["target"]
        comparison = ("business_right_distance" if tag in ("short80", "continuous100", "above101")
                      else "signal_continuity" if tag == "interrupted" else "regardless_weather")
        cases.append({"case_id": row["case_id"], "target_law_id": law,
            "target_type": target_type,
            "rationale": "Requested signal target; actual traveled distance, continuity and course-change onset require saved Native measurement.",
            "variable_assignments": {name: {"kind": kind, "value": values[name]}
                                     for name, kind in variables.items()},
            "unresolved_judgment_calls": [], "paired_probe_id": comparison,
            "deliberate_differences": ["signal_start_distance_ft" if comparison == "business_right_distance"
                                      else "signal_continuity_request" if comparison == "signal_continuity"
                                      else "weather_request"],
            "probe": {"primary_variable": "signal_start_distance_ft" if comparison == "business_right_distance"
                      else "signal_continuity_request" if comparison == "signal_continuity" else "weather_request",
                      "comparison_or_standard": "100 ft business-district continuous signal requirement and source-measured onset",
                      "target_value_or_branch": values["signal_start_distance_ft"] if comparison == "business_right_distance"
                      else values["signal_continuity_request"] if comparison == "signal_continuity" else values["weather_request"]},
            "recording_description": description[row["case_id"]]})
    case_ref = dump("cases.json", {"cell_id": cell, "actor": actor, "status": "draft",
                                    "cases": cases, "sweep_specs": []})
    source = REPO / "inputs" / aid / "assignment.json"
    dump("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": aid,
        "source": {"path": str(source.relative_to(REPO)), "sha256": sha(source)},
        "stages": {"relevance_batch": relevance, "relevance": relevance,
                   "template": template, "judgment_observables": [],
                   "bindings": bindings, "cases": case_ref},
        "status": "draft_original_site_review_pending"})


if __name__ == "__main__":
    main()
