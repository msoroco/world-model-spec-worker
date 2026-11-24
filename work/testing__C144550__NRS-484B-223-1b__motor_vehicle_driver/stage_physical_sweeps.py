"""Expand and mechanically validate proposed finite physical sweeps in scratch."""

import copy
import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STAGE = ROOT / ".runtime-work" / "c144550-physical-sweeps"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not output_root or not Path(output_root).resolve().is_relative_to(ROOT / ".runtime-work"):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
    from scenario_pipeline.batch_pipeline.sweeps import expand_sweeps, grid
    from scenario_pipeline.batch_pipeline.validation import coverage, observable_requirements

    design = json.loads((HERE / "physical-sweep-design.json").read_text())
    cases = json.loads((HERE / "proposals/cases.json").read_text())
    bindings = json.loads((HERE / "proposals/bindings.json").read_text())
    template = json.loads((HERE / "proposals/template.json").read_text())
    observations = [json.loads((HERE / "proposals" / f"judgment-observables-{i}.json").read_text()) for i in (1, 2)]
    by_phrase = {j["phrase"]: j for j in observations}
    for judgment in template["structure"]["judgment_calls_needed"]:
        judgment["observable_requirements"] = copy.deepcopy(by_phrase[judgment["phrase"]]["observable_requirements"])
    for observation, axis, unit, description in (
        (observations[0], design["signal"]["axis"], "frames", "Measured appropriate lamp onset lead relative to first complete body departure."),
        (observations[1], design["gap"]["axis"], "m", "Measured nearest target-lane actor body gap at first complete body departure."),
    ):
        observation["observable_requirements"]["sweep_dimensions"].append({"name": axis, "unit": unit, "description": description})
        observable_requirements(observation["observable_requirements"])
        next(j for j in template["structure"]["judgment_calls_needed"] if j["phrase"] == observation["phrase"])["observable_requirements"] = copy.deepcopy(observation["observable_requirements"])
        bindings["variable_parameters"].append({
            "kind": "controller" if unit == "frames" else "world_setup",
            "name": axis,
            "range_or_domain": "source-bound finite physical sampling range; no legal threshold",
            "used_by_laws": [template["law_id"]],
        })

    before = next(c for c in cases["cases"] if c["case_id"].endswith("__left_signal_before_clear_gap"))
    late = next(c for c in cases["cases"] if c["case_id"].endswith("__left_signal_late_clear_gap"))
    zero = copy.deepcopy(late)
    zero["case_id"] = HERE.name + "__left_signal_at_departure_clear_gap"
    zero["rationale"] = "Appropriate lamp first sampled at complete body departure; legal judgment unresolved."
    zero["variable_assignments"]["signal_timing"]["value"] = "indicator first observed at source-lane body departure"
    cases["cases"].append(zero)
    base_recording = copy.deepcopy(before["recording_description"])
    def recording(axis, unit, method):
        value = copy.deepcopy(base_recording)
        value["channels"].append({
            "name": axis, "unit": unit, "method": method,
            "time_window": "first complete-body source-lane departure in all 900 original frames",
            "reference_frame": "Native frame", "sampling_rate_hz": 20,
            "uncertainty": "Between-frame timing and actual Native behavior remain unproved",
        })
        return value
    def spec(old, axis, unit, bounds, spacing, baseline, method, evidence):
        value = copy.deepcopy(old)
        value.pop("missing_inputs", None)
        value["status"] = "complete"
        value["mode"] = "one_dimensional"
        value["axes"] = [{
            "variable": axis, "observable": axis, "unit": unit,
            "min": bounds[0], "max": bounds[1], "spacing": spacing,
            "range_rationale": "Measured source-backed endpoints; physical coverage only",
            "spacing_rationale": "Include the observed endpoint and intervening landmark" if unit == "frames" else "Use the two source-observed gaps",
            "feasibility_evidence": evidence,
            "measurement": {"method": method,
                            "time_window": "first complete-body source-lane departure",
                            "statistic": "first"},
        }]
        value["landmarks"] = [{"name": "source-observed physical endpoints",
                               "source": evidence,
                               "verification_evidence": "physical-sweep-design.json",
                               "purpose": "coverage_landmark"}]
        value["variable_assignments"] = copy.deepcopy(baseline["variable_assignments"])
        value["variable_assignments"][axis] = {
            "kind": "controller" if unit == "frames" else "world_setup",
            "value": bounds[0], "note": "Physical setpoint; realized observation measured separately",
        }
        value["recording_description"] = recording(axis, unit, method)
        return value
    cases["sweep_specs"] = [
        spec(cases["sweep_specs"][0], design["signal"]["axis"], "frames", [-1, 1], 1,
             before, design["signal"]["measurement"], "judgment-grid-landmarks.json and zero-exact-candidate-replay.json"),
        spec(cases["sweep_specs"][1], design["gap"]["axis"], "m", [3.0, 8.0], 5.0,
             before, design["gap"]["measurement"], "judgment-grid-landmarks.json"),
    ]
    expand_sweeps(cases, [template], bindings)
    coverage(cases["cases"], bindings, [template], cases["sweep_specs"])
    if [c[design["signal"]["axis"]] for c in grid(cases["sweep_specs"][0])] != design["signal"]["selection_order"]:
        raise ValueError("Signal generated order changed")
    if [c[design["gap"]["axis"]] for c in grid(cases["sweep_specs"][1])] != design["gap"]["selection_order"]:
        raise ValueError("Gap generated order changed")
    write(STAGE / "cases.json", cases)
    write(STAGE / "bindings.json", bindings)
    write(STAGE / "template.json", template)
    for number, observation in enumerate(observations, 1):
        write(STAGE / f"judgment-observables-{number}.json", observation)
    result = {"format": "worker-c144550-staged-physical-sweeps",
              "design_sha256": hashlib.sha256((HERE / "physical-sweep-design.json").read_bytes()).hexdigest(),
              "case_ids": [c["case_id"] for c in cases["cases"] if c.get("sweep_id")],
              "selection_order": {s["sweep_id"]: s["selection_order"] for s in cases["sweep_specs"]},
              "generated_case_count": sum(s["planned_case_count"] for s in cases["sweep_specs"]),
              "staged_only": True, "selected_delivery_proofs_complete": False,
              "legal_acceptance_claimed": False}
    write(HERE / "physical-sweep-stage-proof.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
