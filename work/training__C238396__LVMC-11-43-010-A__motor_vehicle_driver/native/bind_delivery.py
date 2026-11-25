"""Bind completed CPU proofs without claiming original Native acceptance."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work"
ASSIGNMENT = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return str(target.relative_to(HERE))


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    tests = []
    selected_proofs = []
    for letter, entry in zip("ab", manifest["cases"]):
        condition = "probe_" + letter
        case = entry["case_id"]
        directory = HERE / "proofs" / condition
        for candidate in ("primary", "fallback1"):
            public = SCRATCH / f"c238396-public-{letter}-{candidate}-v3"
            offline = SCRATCH / f"c238396-final-offline-{condition}-{candidate}/offline.log"
            proofdir = directory / ("public-" + candidate)
            receipt = copy(public / "compatibility.json", proofdir / "receipt.json")
            analysis = copy(public / "compatibility-analysis.log", proofdir / "analysis.log")
            negative = copy(public / "negative-analysis.log", proofdir / "negative.log")
            static = copy(offline, proofdir / "static.log")
            compat = {"receipt": receipt, "sha256": sha(HERE / receipt),
                      "log": analysis, "negative_log": negative}
            construction_sha = (entry["construction_sha256"] if candidate == "primary"
                                else entry["candidates"][0]["construction_sha256"])
            offline_proof = {"command": f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --candidate {candidate} --output .runtime-work/c238396-final-offline-{condition}-{candidate}",
                             "construction_sha256": construction_sha,
                             "exit_code": 0, "log": static,
                             "log_sha256": sha(HERE / static)}
            target = entry if candidate == "primary" else entry["candidates"][0]
            target["compatibility"] = compat
            target["offline"] = offline_proof
            tests.extend([
                {"command": f"runtime.py offline --case {case} --candidate {candidate}",
                 "exit_code": 0, "log": static, "sha256": sha(HERE / static)},
                {"command": f"runtime.py compatibility --case {case} --candidate {candidate}",
                 "exit_code": 0, "log": analysis, "sha256": sha(HERE / analysis)}])
            if candidate == "primary":
                entry["negative"] = {"log": negative}
        saved = copy(SCRATCH / f"c238396-saved-output-{letter}/v0001/processing.json",
                     directory / "saved-processing.json")
        entry["post_capture"] = {
            "recorded_only": True,
            "command": f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --attempt \"$ATTEMPT\" --output \"$OUTPUT\" --library runtime/library --validator \"$DECODER\"",
            "feedback_command": f"inspect \"$OUTPUT/v0001/feedback.json\" for {case} on failure",
            "test_exit_code": 0, "test_log": saved,
            "test_log_sha256": sha(HERE / saved)}
        tests.append({"command": f"runtime.py process-saved --case {case}",
                      "exit_code": 0, "log": saved, "sha256": sha(HERE / saved)})
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
        channels = {c["name"] for c in construction["recording_description"]["channels"]}
        atoms = set(config.get("required_atoms", [])) | channels
        entry["acquisition"] = {atom: {
            "entrypoint": "finalize.py",
            "method": "saved-only exact original actor/map/frame source join and signed radial position change",
            "evidence": "native-raw-actors.jsonl; control-intent.jsonl; roundabout-map-readback.json; video_frames.jsonl; four camera videos"}
            for atom in sorted(atoms)}
        physical = f"proofs/physical/{condition}/proof.json"
        entry["physical_preparation"] = {"receipt": physical,
                                         "sha256": sha(HERE / physical)}
        pos = copy(SCRATCH / f"c238396-delivery-{letter}.log",
                   directory / "delivery-positive.log")
        neg = copy(SCRATCH / f"c238396-delivery-negative-{letter}.log",
                   directory / "delivery-negative.log")
        command = f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py --case {case} --attempt .runtime-work/c238396-saved-attempt-{letter} --processing .runtime-work/c238396-saved-output-{letter}/v0001/processing.json --output .runtime-work/c238396-delivery-{letter}.json --diagnostic"
        negative_command = f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py --case {case} --attempt .runtime-work/c238396-saved-attempt-{letter} --processing .runtime-work/c238396-negative-processing-{letter}.json --output .runtime-work/c238396-delivery-negative-{letter}.json --diagnostic"
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
            "command": command, "test_exit_code": 0,
            "test_log": pos, "test_log_sha256": sha(HERE / pos),
            "negative_command": negative_command, "negative_exit_code": 1,
            "negative_expected_error": "Original source missing or stale: roundabout-map-readback.json",
            "negative_log": neg, "negative_log_sha256": sha(HERE / neg)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        entry["delivery_readiness"] = "cpu_prepared_original_source_pending"
        tests.append({"command": f"delivery_audit.py --case {case} --diagnostic",
                      "exit_code": 0, "log": pos, "sha256": sha(HERE / pos)})
        selected_proofs.append({"case_id": case,
            "construction_sha256": entry["construction_sha256"],
            "primary_compatibility_sha256": entry["compatibility"]["sha256"],
            "fallback_construction_sha256": entry["candidates"][0]["construction_sha256"],
            "fallback_compatibility_sha256": entry["candidates"][0]["compatibility"]["sha256"],
            "saved_processing_sha256": sha(HERE / saved),
            "physical_fixture_proof_sha256": sha(HERE / physical)})
    manifest["status"] = "cpu_prepared_original_source_pending"
    write(manifest_path, manifest)
    pos = copy(SCRATCH / "c238396-comparison.log", HERE / "proofs/comparison-positive.log")
    neg = copy(SCRATCH / "c238396-comparison-negative.log", HERE / "proofs/comparison-negative.log")
    tests.append({"command": "comparison_audit.py --diagnostic", "exit_code": 0,
                  "log": pos, "sha256": sha(HERE / pos)})
    for case in plan["cases"]:
        case["kind"] = "selected_delivery"
        case["planning_status"] = "cpu_prepared_original_source_pending"
    for comparison in plan["comparisons"]:
        comparison["status"] = "cpu_source_comparison_passed_original_pending"
        comparison["audit"] = pos
        comparison["negative_audit"] = neg
    plan["construction_checkpoint"] = {
        "manifest": "execution-manifest.json", "selected": True,
        "comparison_proof": pos, "comparison_proof_sha256": sha(HERE / pos),
        "original_native_observed": False}
    write(plan_path, plan)
    base = json.loads((HERE / "native/probe_a/construction.json").read_text())
    root_config = json.loads(next(f["content"] for f in base["files"] if f["path"] == "config.json"))
    root_config["supported_case_ids"] = [e["case_id"] for e in manifest["cases"]]
    config_text = json.dumps(root_config, indent=2, ensure_ascii=False) + "\n"
    for item in base["files"]:
        if item["path"] == "config.json":
            item["content"] = config_text
        path = HERE / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["content"])
    write(HERE / "construction.json", base)
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    result.update({"status": "ready", "readiness_kind": "delivery_prepared",
                   "reason": "CPU delivery package prepared; original Native capture, actual pixels, roundabout occupancy, physical motion and legal applicability remain pending at GPU delivery.",
                   "counts": {"source_topics": 2,
                              "selected_comparison_cases_planned": 2,
                              "delivery_cases_prepared": 2, "candidates_proven": 4,
                              "comparisons_planned": 1,
                              "accepted_membership_rows": 0,
                              "accepted_equivalence_reuses": 0},
                   "current_cpu_proof": {"format": "c238396-selected-cpu-delivery-proof-v1",
                       "manifest_sha256": sha(manifest_path),
                       "semantic_index_sha256": sha(HERE / "proposals/semantic-index.json"),
                       "selected_cases": selected_proofs,
                       "comparison_positive_sha256": sha(HERE / pos),
                       "comparison_negative_sha256": sha(HERE / neg),
                       "native_executed": False, "physical_acceptance_claimed": False,
                       "legal_verdict_claimed": False},
                   "tests": tests, "candidate_plans_proven": 4,
                   "cases_selected": 2, "comparison_audits_passed": 1,
                   "carla_executed": False, "recordings_accepted": 0,
                   "first_gpu_delivery_command":
                       f"PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange execute-delivery --repo . --batch full-train-delivery --db $DB --assignment {ASSIGNMENT} --case {manifest['cases'][0]['case_id']} --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT"})
    write(result_path, result)
    print(json.dumps({"manifest_sha256": sha(manifest_path),
                      "result_sha256": sha(result_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
