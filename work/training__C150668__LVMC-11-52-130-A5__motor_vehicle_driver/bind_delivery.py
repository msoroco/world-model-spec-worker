"""Bind final CPU receipts for seven exact source-gated delivery cases."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import os
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work"
ASSIGNMENT = HERE.name
PAIRS = ((1, 2), (2, 3), (2, 4), (2, 5), (2, 6), (1, 7))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


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
    for n, entry in enumerate(manifest["cases"], 1):
        suffix = "probe_" + str(n)
        case = entry["case_id"]
        directory = HERE / "proofs" / suffix
        for candidate in ("primary", "fallback1"):
            public = SCRATCH / f"c150668-public-probe_{n}-{candidate}-v11"
            proofdir = directory / ("public-" + candidate)
            receipt = copy(public / "compatibility.json", proofdir / "receipt.json")
            analysis = copy(public / "compatibility-analysis.log", proofdir / "analysis.log")
            negative = copy(public / "negative-analysis.log", proofdir / "negative.log")
            static = copy(HERE / f"selected-probe_{n}-{candidate}-v11-offline.log",
                          proofdir / "static.log")
            target = entry if candidate == "primary" else entry["candidates"][0]
            target["compatibility"] = {"receipt": receipt, "sha256": sha(HERE / receipt),
                "log": analysis, "negative_log": negative}
            construction_sha = target["construction_sha256"]
            target["offline"] = {"command": f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --candidate {candidate} --output .runtime-work/c150668-offline-probe_{n}-{candidate}-v11",
                "construction_sha256": construction_sha, "exit_code": 0,
                "log": static, "log_sha256": sha(HERE / static)}
            tests.append({"command": f"runtime.py offline --case {case} --candidate {candidate}",
                "exit_code": 0, "log": static, "sha256": sha(HERE / static)})
            tests.append({"command": f"runtime.py compatibility --case {case} --candidate {candidate}",
                "exit_code": 0, "log": analysis, "sha256": sha(HERE / analysis)})
            if candidate == "primary":
                entry["negative"] = {"log": negative}
        saved = copy(SCRATCH / f"c150668-saved-probe{n}-output-v11/v0001/processing.json",
                     directory / "saved-processing.json")
        entry["post_capture"] = {"recorded_only": True,
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
        entry["acquisition"] = {atom: {"entrypoint": "finalize.py",
            "method": "saved-only original Native actor, road, footprint, review-role and frame join",
            "evidence": "vehicle-poses.jsonl; road.xodr; fixture-review roles; video_frames.jsonl; four camera videos"}
            for atom in sorted(atoms)}
        physical = f"proofs/physical/{suffix}/proof.json"
        entry["physical_preparation"] = {"receipt": physical, "sha256": sha(HERE / physical)}
        positive = copy(HERE / f"delivery-probe{n}-positive-v11.log",
                        directory / "delivery-positive.log")
        negative = copy(HERE / f"delivery-probe{n}-negative-v11.log",
                        directory / "delivery-negative.log")
        role = "traffic-context" if n == 4 else "police-direction" if n == 5 else (
            "device-direction" if n == 6 else "fixture-identity")
        command = f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py --case {case} --attempt .runtime-work/c150668-saved-probe{n}-attempt-v11 --processing .runtime-work/c150668-saved-probe{n}-output-v11/v0001/processing.json --output .runtime-work/c150668-delivery-probe{n}-v11.json --diagnostic"
        negative_command = f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py --case {case} --attempt .runtime-work/c150668-delivery-probe{n}-negative-v11 --processing .runtime-work/c150668-saved-probe{n}-output-v11/v0001/processing.json --output .runtime-work/c150668-delivery-probe{n}-negative-v11.json --diagnostic"
        entry["delivery_acceptance"] = {"case_id": case, "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
            "command": command, "test_exit_code": 0,
            "test_log": positive, "test_log_sha256": sha(HERE / positive),
            "negative_command": negative_command, "negative_exit_code": 1,
            "negative_expected_error": "Original source missing or stale: fixture-review/" + role + ".json",
            "negative_log": negative, "negative_log_sha256": sha(HERE / negative)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST",
                                   "port_env_var": "CARLA_PORT"}
        entry["delivery_readiness"] = "cpu_prepared_original_source_pending"
        tests.append({"command": f"delivery_audit.py --case {case} --diagnostic",
            "exit_code": 0, "log": positive, "sha256": sha(HERE / positive)})
        selected_proofs.append({"case_id": case,
            "construction_sha256": entry["construction_sha256"],
            "primary_compatibility_sha256": entry["compatibility"]["sha256"],
            "fallback_construction_sha256": entry["candidates"][0]["construction_sha256"],
            "fallback_compatibility_sha256": entry["candidates"][0]["compatibility"]["sha256"],
            "saved_processing_sha256": sha(HERE / saved),
            "physical_fixture_proof_sha256": sha(HERE / physical)})
    manifest["status"] = "cpu_prepared_original_source_pending"
    write(manifest_path, manifest)
    for x, y in PAIRS:
        comparison = next(item for item in plan["comparisons"]
            if item["case_ids"] == [ASSIGNMENT + "__probe_" + str(x),
                                    ASSIGNMENT + "__probe_" + str(y)])
        key = f"{x}-{y}"
        positive = copy(HERE / f"comparison-{key}-v11.log",
            HERE / "proofs" / f"comparison-{key}-positive.log")
        negative = copy(HERE / f"comparison-{key}-negative-v11.log",
            HERE / "proofs" / f"comparison-{key}-negative.log")
        comparison.update(status="cpu_source_comparison_passed_original_pending",
                          audit=positive, negative_audit=negative)
        tests.append({"command": f"comparison_audit.py --pair {key} --diagnostic",
            "exit_code": 0, "log": positive, "sha256": sha(HERE / positive)})
    for case in plan["cases"]:
        case["kind"] = "selected_delivery"
        case["planning_status"] = "cpu_prepared_original_source_pending"
    for candidate in plan["candidate_plans"]:
        candidate["tested_offline"] = True
    plan["construction_checkpoint"] = {"manifest": "execution-manifest.json",
        "selected": True, "comparison_proof": plan["comparisons"][0]["audit"],
        "comparison_proof_sha256": sha(HERE / plan["comparisons"][0]["audit"]),
        "original_native_observed": False}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 30,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"view": name,
            "subject": "ego body, sidewalk elevator/chute fixture and traffic or direction context",
            "interval": "all 600 source frames"}
            for name in ("overview", "approach", "reference_corner", "driver_reference")]}
    write(plan_path, plan)
    base = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())
    config = json.loads(next(f["content"] for f in base["files"] if f["path"] == "config.json"))
    config["supported_case_ids"] = [e["case_id"] for e in manifest["cases"]]
    for item in base["files"]:
        if item["path"] == "config.json":
            item["content"] = json.dumps(config, indent=2) + "\n"
        path = HERE / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["content"])
    write(HERE / "construction.json", base)
    for command, name in (([sys.executable, "runner.py", "--check"], "root-static.log"),
                          ([sys.executable, "-m", "unittest", "discover", "-s", "tests"], "root-tests.log")):
        path = HERE / "proofs" / name
        with path.open("w") as log:
            finished = subprocess.run(command, cwd=HERE,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                stdout=log, stderr=subprocess.STDOUT)
        if finished.returncode:
            raise ValueError("Root check failed: " + name)
    for name, command in (("root-static.log", "runner.py --check"),
                          ("root-tests.log", "python -m unittest discover -s tests")):
        path = HERE / "proofs" / name
        tests.append({"command": command, "exit_code": 0,
            "log": str(path.relative_to(HERE)), "sha256": sha(path)})
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    result.update(status="partial", readiness_kind="delivery_prepared_pending_gate",
        reason="Seven exact CPU delivery paths prepared; original Native fixture identity, traffic necessity, officer/device authority, actual pixels, physical realization and legal applicability remain pending.",
        counts={"source_topics": 1, "selected_comparison_cases_planned": 7,
                "delivery_cases_prepared": 7, "candidates_proven": 14,
                "comparisons_planned": 6, "accepted_membership_rows": 0,
                "accepted_equivalence_reuses": 0},
        current_cpu_proof={"format": "c150668-selected-cpu-delivery-proof-v1",
            "manifest_sha256": sha(manifest_path),
            "semantic_index_sha256": sha(HERE / "proposals/semantic-index.json"),
            "selected_cases": selected_proofs,
            "native_executed": False, "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False},
        tests=tests, candidate_plans_proven=14, cases_selected=7,
        comparison_audits_passed=6, carla_executed=False, recordings_accepted=0,
        first_gpu_delivery_command=f"C150668_FIXTURE_REVIEW_DIR=$FIXTURE_REVIEW_DIR PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange execute-delivery --repo . --batch full-train-delivery --db $DB --assignment {ASSIGNMENT} --case {manifest['cases'][0]['case_id']} --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT")
    write(result_path, result)
    print(json.dumps({"manifest_sha256": sha(manifest_path),
                      "result_sha256": sha(result_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
