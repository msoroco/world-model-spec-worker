"""Expand a source-bound right-of-way timing sweep as a candidate stage.

The canonical cases stage remains unchanged until exact candidate packages and
their source proofs are built. This file is a reproducible construction input.
"""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "runtime/pipeline"))
from scenario_pipeline.batch_pipeline.sweeps import expand_sweeps, validate_spec


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    stage = read(HERE / "proposals/right-of-way-base.json")
    binding = read(HERE / "proposals/bindings.json")
    proof_path = HERE / "update040-traffic-timing-sweep-proof.json"
    proof = read(proof_path)
    runner = HERE / "native/traffic_timing_sweep_runner.py"
    finalizer = HERE / "native/traffic_timing_sweep_finalize.py"
    control = HERE / "native/traffic_timing_sweep.py"
    if (proof["runner_source_sha256"] != sha(runner) or
            proof["finalizer_source_sha256"] != sha(finalizer) or
            proof["control_source_sha256"] != sha(control) or
            proof["original_native_accepted"] is not False):
        raise ValueError("Sweep control source proof changed")
    source_case = next(c for c in stage["cases"] if
                       c["case_id"].endswith("__traffic_yield_wait"))
    spec = next(s for s in stage["sweep_specs"] if
                s["sweep_id"] == "C110919-right-of-way")
    if spec["status"] != "incomplete":
        raise ValueError("Current canonical sweep is no longer incomplete")
    # Frames 20..60 are 1..3 seconds into the fixed 20-Hz/480-frame capture.
    # The 10-frame increment is an authored half-second resolution, not a
    # supposed legal yield gap. Original CARLA motion may shift or fail.
    spec.update({
        "status": "complete",
        "mode": "one_dimensional",
        "axes": [{
            "variable": "traffic_launch_frame",
            "observable": "ego_minus_traffic_entry_s",
            "unit": "s",
            "min": 20, "max": 60, "spacing": 10,
            "measurement": {
                "method": "saved Native ego and directed-traffic full-body first conflict entry difference",
                "time_window": "entire original 24 s attempt",
                "statistic": "first"
            },
            "range_rationale": "Launch at 1 to 3 s inside a 24 s capture; fixed stop frame 260 leaves 10 to 12 s commanded travel before brake and 11 s afterward.",
            "spacing_rationale": "Ten 20-Hz frames give 0.5 s distinct command changes; this is sampling resolution and has no legal cutoff meaning.",
            "feasibility_evidence": "TrafficLaunch validates all five setpoints against 480 frames and stop frame 260; four candidate runner knob sets pass offline geometry. Source-bound diagnostic proves only frame 30, so physical motion remains unverified."
        }],
        "landmarks": [{
            "name": "diagnostic_launch_30",
            "value": 30, "unit": "frame",
            "source": "update040-traffic-timing-sweep-proof.json",
            "verification_evidence": sha(proof_path),
            "purpose": "coverage_landmark"
        }],
        "rationale": "Sample authored cross-traffic launch while holding ego yield policy and red-turn geometry fixed; measure realized precedence without a legal judgment.",
        "variable_assignments": deepcopy(source_case["variable_assignments"]),
        "recording_description": deepcopy(source_case["recording_description"])
    })
    spec.pop("missing_inputs", None)
    spec["variable_assignments"]["traffic_launch_frame"] = {
        "kind": "controller", "value": 20,
        "note": "Authored command frame; observed conflict timing comes only from retained Native sources"
    }
    spec["recording_description"]["context_inputs"].extend([
        {"name": "traffic_launch_frame", "unit": "frame",
         "method": "Selected exact config and every retained Native sample"},
        {"name": "directed_traffic_signal_and_lane", "unit": "structured",
         "method": "Native signal actor and west-approach lane readback"},
        {"name": "four_source_cameras", "unit": "video",
         "method": "Full 480-frame source decode joined to Native frames"}
    ])
    spec["recording_description"]["channels"].append({
        "name": "ego_minus_traffic_entry_s", "unit": "s",
        "sampling_rate_hz": 20,
        "method": "Postcapture source-derived first-entry difference repeated against each saved Native frame for exact frame joins",
        "time_window": "entire 24 s / 480-frame attempt",
        "reference_frame": "Native full-body conflict zone and exact original frame identity",
        "uncertainty": "50 ms sampling for each first entry; not a legal right-of-way threshold",
    })
    spec["recording_description"]["limitations"].append(
        "Original vehicle trajectories, directed-signal activation and camera visibility require independent review")
    if "traffic_launch_frame" not in {p["name"] for p in binding["variable_parameters"]}:
        binding["variable_parameters"].append({
            "name": "traffic_launch_frame", "kind": "controller",
            "range_or_domain": [20, 30, 40, 50, 60],
            "used_by_laws": ["NRS-484B-307-8a"]
        })
    validate_spec(spec)
    expand_sweeps(stage, [read(HERE / "proposals/template.json")], binding)
    selected = [c for c in stage["cases"] if c.get("sweep_id") == spec["sweep_id"]]
    if len(selected) != 5 or sorted(c["sweep_point"]["traffic_launch_frame"] for c in selected) != [20, 30, 40, 50, 60]:
        raise ValueError("Expanded sweep case set differs")
    stage["candidate_only"] = True
    stage["source_proof_sha256"] = sha(proof_path)
    stage["original_native_accepted"] = False
    output = HERE / "proposals/right-of-way-sweep-candidate.json"
    output.write_text(json.dumps(stage, indent=2) + "\n")
    return output, selected


if __name__ == "__main__":
    output, cases = build()
    print(json.dumps({"candidate_stage": str(output), "sha256": sha(output),
                      "exact_sweep_cases": [c["case_id"] for c in cases],
                      "original_native_accepted": False}))
