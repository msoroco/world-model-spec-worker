"""Author the exact statutory stage chain without making a legal judgment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
INPUT = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
LAW = INPUT["law"]
LAW_ID = LAW["id"]
TEMPLATE_ID = LAW_ID + "@motor_vehicle_driver"
PROPOSALS = HERE / "proposals"


def write(name: str, value: dict) -> None:
    PROPOSALS.mkdir(exist_ok=True)
    (PROPOSALS / name).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(name: str) -> dict:
    path = PROPOSALS / name
    return {"path": str(path.relative_to(HERE)), "sha256": sha(path)}


def main() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    description = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())["recording_description"]
    relevance = {"cell_id": "C261489", "actor": "motor_vehicle_driver", "status": "draft",
                 "relevant_laws": [{"law_id": LAW_ID, "applies_to": ["motor_vehicle_driver"],
                                    "quote": LAW["text"], "confidence": "medium",
                                    "notes": "Original school zone, passing trajectory, calendar, beacon and sign need source review."}],
                 "borderline_excluded": []}
    write("relevance.json", relevance)
    write("relevance_batch.json", relevance)
    clauses = [
        "On a day on which the school is not in session",
        "During the period from a half hour after school is no longer in operation to a half hour before school is next in operation",
        "If the zone is designated by an operational speed limit beacon, during the hours when the pupils of the school are in class and the yellow lights of the speed limit beacon are not flashing in the manner which indicates that the speed limit is in effect",
        "If the zone is not designated by an operational speed limit beacon, during the times when the sign designating the school zone or school crossing zone indicates that the speed limit is not in effect",
    ]
    parameters = [
        ("pass_requested", "controller", "true or false passing-route request"),
        ("pass_location", "world_setup", "inside or outside surveyed designated zone"),
        ("school_session", "world_setup", "independent school-calendar true or false"),
        ("minutes_after_last_operation_end", "world_setup", "source-clock minutes from prior school-operation end"),
        ("minutes_before_next_operation_start", "world_setup", "source-clock minutes until next school-operation start"),
        ("during_pupil_class_hours", "world_setup", "independent class schedule true or false"),
        ("beacon_operational", "world_setup", "original device operational state"),
        ("beacon_alternating_flash", "world_setup", "original two-lamp alternating indication"),
        ("sign_limit_active", "world_setup", "source-reviewed sign instruction"),
    ]
    refs = [{"name": name, "kind": kind, "range_or_domain": domain} for name, kind, domain in parameters]
    judgments = [
        ("area designated as a school zone or school crossing zone", "Surveyed designated zone and school property adjacency need original map and sign sources.", "designated_zone_extent"),
        ("overtake and pass another vehicle traveling in the same direction", "Completion depends on original two-vehicle trajectories and body geometry.", "same_direction_pass"),
        ("school is not in session", "Session depends on independent school calendar and civil time.", "school_schedule_and_clock"),
        ("school is no longer in operation", "Operation endpoints and half-hour offsets need source clock and schedule.", "school_schedule_and_clock"),
        ("operational speed limit beacon", "Sign, two or more yellow lights, alternating capability, governance and operation need original source/device readback.", "beacon_sign_readback"),
        ("pupils of the school are in class", "Class hours require an independent pupil schedule joined to original local time.", "school_schedule_and_clock"),
        ("yellow lights of the speed limit beacon are not flashing", "Actual alternating indication needs synchronized lamp samples, not a requested setting.", "beacon_sign_readback"),
        ("sign designating the school zone or school crossing zone indicates that the speed limit is not in effect", "Exact sign instruction and nonbeacon governance need original source review.", "beacon_sign_readback"),
    ]
    template = {
        "template_id": TEMPLATE_ID, "law_id": LAW_ID, "actor": "motor_vehicle_driver",
        "quote": LAW["text"], "parameter_refs": refs,
        "structure": {
            "law_id": LAW_ID,
            "activation": {"condition": "Driver overtakes and passes another same-direction vehicle inside a designated school zone or school crossing zone.", "numeric_conditions": []},
            "obligation": {"type": "must_not", "description": "Driver shall not overtake and pass inside the designated area unless a stated exception applies.", "numeric_conditions": []},
            "exceptions": [{"trigger": clause, "source_clause": clause,
                            "effect": "Exception applicability requires original source review",
                            "replacement_obligation": "none claimed"} for clause in clauses],
            "timing": {"description": "Independent school day, operation and pupil class hours, local time, beacon and sign intervals. Thirty-minute boundaries are measured without resolving legal equality.",
                       "numeric_conditions": [
                           {"variable": "minutes_after_last_operation_end", "operator": ">=", "value": 30, "unit": "min"},
                           {"variable": "minutes_before_next_operation_start", "operator": ">=", "value": 30, "unit": "min"},
                       ]},
            "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note, _ in judgments],
        },
    }
    write("template.json", template)
    judgment_files = []
    for index, (phrase, note, channel) in enumerate(judgments, 1):
        need = {"name": channel, "unit": "structured", "description": "Original Native readback and independent reviewed source."}
        context = {"name": "reviewed_original_school_sources", "unit": "source",
                   "description": "Sealed original school, zone, sign and device source bytes."}
        write(f"judgment_observables_{index}.json", {
            "template_id": TEMPLATE_ID, "phrase": phrase, "note": note,
            "observable_requirements": {"observables": [need], "recording_needs": [need],
                                        "context_inputs": [context], "sweep_dimensions": [],
                                        "landmarks": [], "limitations": ["Physical source and legal meaning remain independently reviewable."]},
        })
        judgment_files.append(f"judgment_observables_{index}.json")
    bindings = {
        "cell_id": "C261489", "actor": "motor_vehicle_driver", "status": "draft",
        "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
        "context_refs": [], "established_contexts": ["Assigned school-zone passing and operational beacon context; physical designation requires original review."],
        "fixed_parameters": [],
        "variable_parameters": [dict(value, used_by_laws=[LAW_ID]) for value in refs],
    }
    write("bindings.json", bindings)
    defaults = {
        "pass_requested": True, "pass_location": "inside", "school_session": True,
        "minutes_after_last_operation_end": -60, "minutes_before_next_operation_start": 1080,
        "during_pupil_class_hours": True, "beacon_operational": True,
        "beacon_alternating_flash": True, "sign_limit_active": True,
    }
    names = [phrase for phrase, _, _ in judgments]
    case_rows = []
    variations = {
        "school_not_in_session": {"school_session": False},
        "after_end_29m": {"minutes_after_last_operation_end": 29},
        "after_end_30m": {"minutes_after_last_operation_end": 30},
        "after_end_31m": {"minutes_after_last_operation_end": 31},
        "before_start_31m": {"minutes_before_next_operation_start": 31},
        "before_start_30m": {"minutes_before_next_operation_start": 30},
        "before_start_29m": {"minutes_before_next_operation_start": 29},
        "class_no_flash": {"beacon_alternating_flash": False},
        "sign_without_operational_beacon": {"beacon_operational": False,
                                            "beacon_alternating_flash": False,
                                            "sign_limit_active": False},
        "no_pass": {"pass_requested": False},
        "outside_zone": {"pass_location": "outside"},
    }
    def assignments(changes):
        values = dict(defaults, **changes)
        return {name: {"kind": kind, "value": values[name]} for name, kind, _ in parameters}
    case_rows.append({"case_id": ASSIGNMENT + "__baseline_reference", "target_law_id": None,
                      "target_type": "baseline", "rationale": "Planning reference; no additional capture or legal judgment.",
                      "variable_assignments": assignments({}), "recording_description": description,
                      "unresolved_judgment_calls": names})
    for plan_case in plan["cases"]:
        case_id = plan_case["case_id"]
        name = case_id[len(ASSIGNMENT) + 2:]
        changed = variations.get(name, {})
        key = next(iter(changed), "pass_requested")
        target_type = "boundary_probe" if name.startswith(("after_end_", "before_start_")) else "judgment_sweep"
        probe = {"primary_variable": key,
                 "comparison_or_standard": "source-reviewed statutory branch or measured physical activation",
                 "target_value_or_branch": name}
        if target_type == "boundary_probe":
            after = name.startswith("after_end_")
            probe.update(threshold_ref="timing.numeric_conditions[0]" if after else "timing.numeric_conditions[1]",
                         operator=">=", unit="min", test_value=int(name.split("_")[-1][:-1]))
        row = {"case_id": case_id, "target_law_id": LAW_ID, "target_type": target_type,
               "rationale": "Exact source-gated school-zone same-direction passing case: " + name,
               "paired_probe_id": "after_end_boundary" if name.startswith("after_end_") else
                                  "before_start_boundary" if name.startswith("before_start_") else
                                  "school_pass_controls",
               "deliberate_differences": list(changed) or ["pass_requested"],
               "probe": probe, "variable_assignments": assignments(changed),
               "recording_description": description, "unresolved_judgment_calls": names}
        if target_type == "boundary_probe":
            row["epsilon_used"] = 1
        case_rows.append(row)
    write("cases.json", {"cell_id": "C261489", "actor": "motor_vehicle_driver",
                         "status": "draft", "cases": case_rows,
                         "sweeps_expanded": True,
                         "sweep_specs": [{"sweep_id": "source_pending_school_pass_judgments",
                                          "target_law_id": LAW_ID, "status": "incomplete",
                                          "judgment_refs": [{"phrase": phrase, "note": note} for phrase, note, _ in judgments],
                                          "missing_inputs": ["Original surveyed school-zone, passing-route, calendar, beacon and sign packets"],
                                          "rationale": "Physical source documents absent from worker export; qualitative legal cutoffs are not invented."}]})
    write("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
                                  "stages": {"relevance_batch": ref("relevance_batch.json"),
                                             "relevance": ref("relevance.json"),
                                             "template": ref("template.json"),
                                             "judgment_observables": [ref(name) for name in judgment_files],
                                             "bindings": ref("bindings.json"),
                                             "cases": ref("cases.json")}})
    print(json.dumps({"stages": 5 + len(judgments), "selected_cases": len(plan["cases"])}))


if __name__ == "__main__":
    main()
