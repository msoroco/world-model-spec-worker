"""Bind the first exact case to its selected saved-source software proof."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + "__traveling_follow_500ft"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    construction_path = HERE / "construction.json"
    construction = json.loads(construction_path.read_text())
    config = json.loads((HERE / "config.json").read_text())
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    requirement = "following a traveling fire apparatus at the 500 ft boundary"
    source = "NRS 484B.710 full text in inputs/" + HERE.name + "/assignment.json"
    disposition = {"requirement": requirement, "source": source,
                   "status": "selected_required", "case_ids": [CASE],
                   "evidence_or_gap": "Original full-body Native footprints and participant state are required; accepted 450/550 ft recordings do not establish at-500 behavior."}
    if "requirement_dispositions" not in plan:
        plan["requirement_dispositions"] = [disposition]
        put(plan_path, plan)
    elif plan["requirement_dispositions"][0] != disposition:
        raise ValueError("Existing requirement disposition changed")
    inputs = ["video_frames.jsonl", "trace.jsonl",
              "participant_footprints.jsonl", "participant_state.jsonl",
              "fire_context.json"]
    contract = {
        "format": "worker-measurement-contract", "case_id": CASE,
        "requirements": [{"disposition_index": 0,
                          "requirement": requirement, "source": source,
                          "output_key": "fire_boundary_observation",
                          "method": "measure_fire_branch", "value_type": "object",
                          "kind": "measured", "inputs": inputs}],
        "negative": {"remove": ["participant_state.jsonl"],
                     "error_contains": "Missing required source: participant_state.jsonl"},
    }
    put(HERE / "first-measurement-contract.json", contract)
    proposal = {"format": "scenario-coverage-cases", "status": "draft",
                "cell_id": "C102304", "actor": "motor_vehicle_driver",
                "sweep_specs": [], "cases": [{
                    "case_id": CASE, "target_law_id": "NRS-484B-710",
                    "target_type": "boundary_probe", "rationale": requirement,
                    "variable_assignments": {"target_distance_ft": {"kind": "controller", "value": 500}},
                    "unresolved_judgment_calls": [],
                    "recording_description": construction["recording_description"],
                }]}
    put(HERE / "proposals/cases.json", proposal)
    runtime = ROOT / "runtime/SOURCE-MANIFEST.json"
    entry = {"case_id": CASE, "kind": "delivery",
             "construction": "construction.json",
             "construction_sha256": digest(construction_path),
             "measurement_contract": "first-measurement-contract.json",
             "measurement_procedure": {"entrypoint": "fire_finalizer.py"},
             "fixture_recipe": "work/" + HERE.name + "/diagnostic-recipe.json",
             "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
             "candidate_risk": {"status": "physical",
                                "reason": "Following control may miss measured full-footprint 500 ft separation on the selected crest"},
             "candidates": []}
    offline = HERE / "first-offline.log"
    if offline.is_file():
        entry["offline"] = {"command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + HERE.name + "/execution-manifest.json --case " + CASE + " --output .runtime-work/fire-first-offline-current --python $PWD/.venv-cpu/bin/python",
                            "exit_code": 0, "log": "first-offline.log",
                            "log_sha256": digest(offline),
                            "construction_sha256": digest(construction_path)}
    compatibility = HERE / "first-compatibility.json"
    if compatibility.is_file():
        entry["compatibility"] = {
            "receipt": compatibility.name, "sha256": digest(compatibility),
            "log": "first-compat.log", "negative_log": "first-negative.log"}
        entry["negative"] = {"log": "first-negative.log"}
        entry["acquisition"] = {"fire_gap_ft": {
            "entrypoint": "fire_finalizer.py",
            "method": "recompute each frame from retained original participant footprints",
            "evidence": "FireCaptureSession writes original footprints/state and synchronized Native frame identities; the finalizer derives the stream after capture."}}
    fallback_file = HERE / "first-fallbacks.json"
    if fallback_file.is_file():
        for fallback in json.loads(fallback_file.read_text()):
            candidate = dict(fallback)
            if digest(HERE / candidate["construction"]) != candidate["construction_sha256"]:
                raise ValueError("Fallback construction changed")
            name = candidate["id"]
            offline_log = HERE / ("first-" + name + "-offline.log")
            if offline_log.is_file():
                candidate["offline"] = {
                    "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + HERE.name + "/execution-manifest.json --case " + CASE + " --candidate " + name + " --output .runtime-work/" + name + "-offline --python $PWD/.venv-cpu/bin/python",
                    "exit_code": 0, "log": offline_log.name,
                    "log_sha256": digest(offline_log),
                    "construction_sha256": candidate["construction_sha256"]}
            receipt = HERE / ("first-" + name + "-compatibility.json")
            if receipt.is_file():
                candidate["compatibility"] = {
                    "receipt": receipt.name, "sha256": digest(receipt),
                    "log": "first-" + name + "-compat.log",
                    "negative_log": "first-" + name + "-negative.log"}
            entry["candidates"].append(candidate)
    tests = HERE / "cpu-tests.log"
    if tests.is_file():
        entry["post_capture"] = {
            "recorded_only": True,
            "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + HERE.name + "/execution-manifest.json --case " + CASE + " --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR",
            "feedback_command": "cat $OUTPUT/v0001/feedback.json",
            "test_log": tests.name, "test_log_sha256": digest(tests),
            "test_exit_code": 0}
    put(HERE / "execution-manifest.json",
        {"format": "worker-execution-manifest", "assignment_id": HERE.name,
         "runtime_manifest_sha256": digest(runtime), "cases": [entry]})


if __name__ == "__main__":
    main()
