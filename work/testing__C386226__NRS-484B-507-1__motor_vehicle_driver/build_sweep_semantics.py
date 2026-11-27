"""Freeze five physical coverage grids while leaving every legal call open."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = "NRS-484B-507-1"


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ROOT / ".runtime-work" not in output.parents:
        raise ValueError("pipeline output must be under .runtime-work")
    sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
    from batch_pipeline.sweeps import expand_sweeps

    directory = HERE / "proposals"
    payload = json.loads((directory / "cases.json").read_text())
    payload["cases"] = [case for case in payload["cases"] if case["target_type"] != "judgment_sweep"]
    payload.pop("sweeps_expanded", None)
    payload.pop("reference_normalizations", None)
    payload.pop("case_contract_normalizations", None)
    template = json.loads((directory / "template.json").read_text())
    bindings = json.loads((directory / "bindings.json").read_text())
    phrases = template["structure"]["judgment_calls_needed"]
    fields = [
        ("material_delay", "activity_delay_s", "halt_to_material_event_s", "s", 1.0, 12.0, 5.5,
         "pickup_load_prompt", "materials_activity", "Original material inventory, actual loading and 900-frame halt-to-task chronology"),
        ("marked_boundary", "zone_boundary_offset_m", "zone_boundary_signed_distance_m", "m", -0.5, 0.5, 0.5,
         "stop_no_material", "marked_freight_zone", "Reviewed marked polygon, curb survey and feasible parking poses"),
        ("effective_hours", "civil_clock_offset_min", "civil_boundary_offset_min", "min", -30.0, 30.0, 30.0,
         "park_outside_hours", "effective_hours", "Applicable provision boundary, original civil clock and timezone"),
        ("passenger_dwell", "passenger_dwell_s", "observed_passenger_dwell_s", "s", 2.0, 10.0, 4.0,
         "passenger_board_clear", "passenger_activity", "Reviewed passenger path and original boarding start/completion events"),
        ("freight_headway", "freight_entry_headway_s", "observed_freight_entry_headway_s", "s", 0.0, 4.0, 2.0,
         "passenger_board_about_to_enter", "freight_vehicle_entry", "Reviewed qualifying materials-transport vehicle route and entry event chronology"),
    ]
    controller = {"zone_boundary_offset_m", "passenger_dwell_s", "freight_entry_headway_s"}
    new_params = [
        ("zone_boundary_offset_m", "controller", "-0.5 through +0.5 m engineering offset from source-reviewed marked boundary", "m"),
        ("zone_boundary_signed_distance_m", "subject_behavior", "measured original halt-position distance to marked polygon", "m"),
        ("civil_clock_offset_min", "world_setup", "-30 through +30 min engineering clock offset from sourced provision boundary", "min"),
        ("civil_boundary_offset_min", "subject_behavior", "measured original civil time offset from sourced provision boundary", "min"),
        ("passenger_dwell_s", "controller", "2 through 10 s engineering passenger activity duration request", "s"),
        ("observed_passenger_dwell_s", "subject_behavior", "measured original boarding event duration", "s"),
        ("freight_entry_headway_s", "controller", "0 through 4 s engineering freight arrival request", "s"),
        ("observed_freight_entry_headway_s", "subject_behavior", "measured original freight approach event time from ego halt", "s"),
        ("halt_to_material_event_s", "subject_behavior", "measured original halt-to-material-task start", "s"),
    ]
    for name, kind, domain, unit in new_params:
        record = {"name": name, "kind": kind, "range_or_domain": domain, "unit": unit}
        if not any(p["name"] == name for p in bindings["variable_parameters"]):
            bindings["variable_parameters"].append(dict(record, used_by_laws=[LAW]))
        if not any(p["name"] == name for p in template["parameter_refs"]):
            template["parameter_refs"].append(record)
    for case in payload["cases"]:
        for name, kind, _, unit in new_params:
            case["variable_assignments"].setdefault(name, {"kind": kind, "value": None, "unit": unit})
    specs = []
    for index, (label, variable, observable, unit, low, high, spacing, anchor, channel, evidence) in enumerate(fields):
        judgment = phrases[index]
        judgment_path = directory / f"judgment-{index}.json"
        judgment_proposal = json.loads(judgment_path.read_text())
        judgment_proposal["observable_requirements"]["sweep_dimensions"] = [{
            "name": observable, "unit": unit,
            "description": "Original-source engineering coverage measurement; no legal cutoff or verdict"}]
        write(judgment_path, judgment_proposal)
        source = next(c for c in payload["cases"] if c["case_id"] == AID + "__" + anchor)
        assignments = json.loads(json.dumps(source["variable_assignments"]))
        recording = json.loads(json.dumps(source["recording_description"]))
        recording["channels"].append({"name": observable, "unit": unit,
            "method": "original source-joined Native frame and reviewed site",
            "sampling_rate_hz": 20,
            "time_window": "all 900 original frames",
            "reference_frame": "original Native frame and reviewed freight curb geometry",
            "uncertainty": "Synthetic fixture does not establish original source or physical visibility"})
        if label == "effective_hours":
            assignments["provisions_effective"] = {"kind": "world_setup", "value": None,
                "unit": "boolean", "note": "read back from reviewed provision and original civil clock"}
        assignments[variable] = {"kind": "controller" if variable in controller else "world_setup",
                                 "value": None, "unit": unit}
        specs.append({"sweep_id": AID + "__sweep_" + label,
            "target_law_id": LAW, "judgment_refs": [judgment], "status": "complete",
            "mode": "one_dimensional", "landmarks": [],
            "rationale": "Source-gated three-point engineering coverage of " + label + "; all five legal judgments remain unresolved.",
            "recording_description": recording,
            "variable_assignments": assignments,
            "axes": [{"variable": variable, "observable": observable, "unit": unit,
                "min": low, "max": high, "spacing": spacing,
                "range_rationale": evidence + "; source review is a dispatch precondition, not a CPU fixture claim.",
                "spacing_rationale": "Endpoints and midpoint cover physical variation without a statutory threshold.",
                "feasibility_evidence": evidence + "; original Native site validation rejects missing reviewed sources.",
                "measurement": {"method": "Source-joined original Native 900-frame chronology and reviewed site readback",
                    "time_window": "first original halt through task or entry event within 900 frames",
                    "statistic": "first"}}]})
    payload["sweep_specs"] = specs
    write(directory / "template.json", template)
    write(directory / "bindings.json", bindings)
    expand_sweeps(payload, templates=[template], bindings=bindings)
    write(directory / "cases.json", payload)
    index_path = directory / "semantic-index.json"
    index = json.loads(index_path.read_text())
    for stage, path in (("template", directory / "template.json"),
                        ("bindings", directory / "bindings.json"),
                        ("cases", directory / "cases.json")):
        index["stages"][stage]["sha256"] = sha(path)
    for i in range(5):
        index["stages"]["judgment_observables"][i]["sha256"] = sha(directory / f"judgment-{i}.json")
    write(index_path, index)
    print(json.dumps({"sweep_specs": len(specs), "selected_cases": len(payload["cases"]) - 1}))


if __name__ == "__main__":
    main()
