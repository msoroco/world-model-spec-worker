"""Bind final source-hashed CPU rail delivery receipts and comparison audits."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work"
ASSIGNMENT = HERE.name
PAIRS = (("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return str(target.relative_to(HERE))


def run(command, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as stream:
        finished = subprocess.run(command, cwd=ROOT,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            stdout=stream, stderr=subprocess.STDOUT)
    return finished.returncode


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    tests, selected_proofs = [], []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__probe_", 1)[1]
        proofdir = HERE / "proofs" / ("probe_" + suffix)
        for candidate in ("primary", "fallback1"):
            public = SCRATCH / f"c202463-public-probe-{suffix}-{candidate}-v3"
            directory = proofdir / ("public-" + candidate)
            receipt = copy(public / "compatibility.json", directory / "receipt.json")
            analysis = copy(public / "compatibility-analysis.log", directory / "analysis.log")
            negative = copy(public / "negative-analysis.log", directory / "negative.log")
            static = f"selected-probe-{suffix}-{candidate}-v3-offline.log"
            target = entry if candidate == "primary" else entry["candidates"][0]
            target["compatibility"] = {"receipt": receipt,
                "sha256": sha(HERE / receipt), "log": analysis,
                "negative_log": negative}
            target["offline"] = {"command": f"runtime.py offline --case {case} --candidate {candidate}",
                "construction_sha256": target["construction_sha256"],
                "exit_code": 0, "log": static, "log_sha256": sha(HERE / static)}
            tests.append({"command": f"runtime.py offline --case {case} --candidate {candidate}",
                "exit_code": 0, "log": static, "sha256": sha(HERE / static)})
            tests.append({"command": f"runtime.py compatibility --case {case} --candidate {candidate}",
                "exit_code": 0, "log": analysis, "sha256": sha(HERE / analysis)})
            if candidate == "primary":
                entry["negative"] = {"log": negative}
        processing = SCRATCH / f"c202463-saved-probe-{suffix}-output-v3/v0001/processing.json"
        saved = copy(processing, proofdir / "saved-processing.json")
        entry["post_capture"] = {"recorded_only": True,
            "command": f"runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $DECODER",
            "feedback_command": f"inspect $OUTPUT/v0001/feedback.json for {case} on failure",
            "test_exit_code": 0, "test_log": saved,
            "test_log_sha256": sha(HERE / saved)}
        tests.append({"command": f"runtime.py process-saved --case {case}",
            "exit_code": 0, "log": saved, "sha256": sha(HERE / saved)})
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
        channels = {c["name"] for c in construction["recording_description"]["channels"]}
        atoms = set(config.get("required_atoms", [])) | channels
        entry["acquisition"] = {atom: {"entrypoint": "finalize.py",
            "method": "saved original Native gate, actor footprint, road, lane review and video-frame join",
            "evidence": "actors.jsonl; gate.jsonl; road.xodr; rail-review roles; video_frames.jsonl; four source cameras"}
            for atom in sorted(atoms)}
        physical = f"proofs/physical/probe_{suffix}/proof.json"
        entry["physical_preparation"] = {"receipt": physical, "sha256": sha(HERE / physical)}
        attempt = SCRATCH / f"c202463-saved-probe-{suffix}-attempt-v3"
        audit_out = proofdir / "delivery-diagnostic.json"
        positive_log = proofdir / "delivery-positive.log"
        command = [sys.executable, str(HERE / "delivery_audit.py"),
            "--case", case, "--attempt", str(attempt),
            "--processing", str(processing), "--output", str(audit_out), "--diagnostic"]
        if run(command, positive_log):
            raise ValueError("Positive rail delivery audit failed: " + suffix)
        negative_attempt = SCRATCH / f"c202463-delivery-probe-{suffix}-negative-v3"
        if negative_attempt.exists():
            shutil.rmtree(negative_attempt)
        shutil.copytree(attempt, negative_attempt, copy_function=os.link)
        (negative_attempt / "rail-review/required-stop.json").unlink()
        negative_log = proofdir / "delivery-negative.log"
        negative_command = [sys.executable, str(HERE / "delivery_audit.py"),
            "--case", case, "--attempt", str(negative_attempt),
            "--processing", str(processing), "--output",
            str(SCRATCH / f"c202463-delivery-probe-{suffix}-negative-v3.json"), "--diagnostic"]
        negative_exit = run(negative_command, negative_log)
        expected_error = "Original source missing or stale: rail-review/required-stop.json"
        if negative_exit == 0 or expected_error not in negative_log.read_text():
            raise ValueError("Missing required-stop source did not reject delivery: " + suffix)
        entry["delivery_acceptance"] = {"case_id": case, "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join",
                "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
            "command": " ".join(command), "test_exit_code": 0,
            "test_log": str(positive_log.relative_to(HERE)),
            "test_log_sha256": sha(positive_log),
            "negative_command": " ".join(negative_command),
            "negative_exit_code": negative_exit,
            "negative_expected_error": expected_error,
            "negative_log": str(negative_log.relative_to(HERE)),
            "negative_log_sha256": sha(negative_log)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST",
                                   "port_env_var": "CARLA_PORT"}
        entry["delivery_readiness"] = "cpu_prepared_original_rail_source_pending"
        tests.append({"command": f"delivery_audit.py --case {case} --diagnostic",
            "exit_code": 0, "log": str(positive_log.relative_to(HERE)),
            "sha256": sha(positive_log)})
        selected_proofs.append({"case_id": case,
            "construction_sha256": entry["construction_sha256"],
            "primary_compatibility_sha256": entry["compatibility"]["sha256"],
            "fallback_construction_sha256": entry["candidates"][0]["construction_sha256"],
            "fallback_compatibility_sha256": entry["candidates"][0]["compatibility"]["sha256"],
            "saved_processing_sha256": sha(HERE / saved),
            "physical_fixture_proof_sha256": sha(HERE / physical)})
    manifest["status"] = "cpu_prepared_original_rail_source_pending"
    write(manifest_path, manifest)
    for first, second in PAIRS:
        case_a, case_b = (ASSIGNMENT + "__probe_" + letter for letter in (first, second))
        comparison = next(item for item in plan["comparisons"]
            if item["case_ids"] == [case_a, case_b])
        attempt_a = SCRATCH / f"c202463-saved-probe-{first}-attempt-v3"
        attempt_b = SCRATCH / f"c202463-saved-probe-{second}-attempt-v3"
        processing_a = SCRATCH / f"c202463-saved-probe-{first}-output-v3/v0001/processing.json"
        processing_b = SCRATCH / f"c202463-saved-probe-{second}-output-v3/v0001/processing.json"
        directory = HERE / "proofs/comparisons"
        out = directory / f"{first}-{second}.json"
        positive_log = directory / f"{first}-{second}-positive.log"
        command = [sys.executable, str(HERE / "comparison_audit.py"),
            "--attempt-a", str(attempt_a), "--attempt-b", str(attempt_b),
            "--processing-a", str(processing_a), "--processing-b", str(processing_b),
            "--output", str(out), "--diagnostic"]
        if run(command, positive_log):
            raise ValueError("Rail comparison audit failed: " + first + second)
        negative_log = directory / f"{first}-{second}-negative.log"
        negative_command = list(command)
        negative_command[negative_command.index("--attempt-b") + 1] = str(attempt_a)
        negative_command[negative_command.index("--output") + 1] = str(
            SCRATCH / f"c202463-comparison-{first}-{second}-negative-v3.json")
        negative_exit = run(negative_command, negative_log)
        if negative_exit == 0 or "Rail measurements differ from processing case IDs" not in negative_log.read_text():
            raise ValueError("Rail comparison source-binding negative failed: " + first + second)
        comparison.update(status="cpu_source_comparison_passed_original_pending",
            audit=str(positive_log.relative_to(HERE)),
            negative_audit=str(negative_log.relative_to(HERE)),
            result=str(out.relative_to(HERE)), result_sha256=sha(out))
        tests.append({"command": f"comparison_audit.py --pair {first}-{second} --diagnostic",
            "exit_code": 0, "log": str(positive_log.relative_to(HERE)),
            "sha256": sha(positive_log)})
    plan["construction_checkpoint"] = {"manifest": "execution-manifest.json",
        "selected": True, "comparison_proof": plan["comparisons"][0]["audit"],
        "comparison_proof_sha256": sha(HERE / plan["comparisons"][0]["audit"]),
        "original_native_observed": False}
    write(plan_path, plan)
    base = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())
    for item in base["files"]:
        path = HERE / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["content"])
    write(HERE / "construction.json", base)
    for args, name in (((sys.executable, "runner.py", "--check"), "root-static.log"),
                       ((sys.executable, "-m", "unittest", "discover", "-s", "tests"), "root-tests.log")):
        log = HERE / "proofs" / name
        with log.open("w") as stream:
            status = subprocess.run(args, cwd=HERE,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                stdout=stream, stderr=subprocess.STDOUT)
        if status.returncode:
            raise ValueError("Root rail construction check failed: " + name)
        tests.append({"command": " ".join(args), "exit_code": 0,
            "log": str(log.relative_to(HERE)), "sha256": sha(log)})
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    result.update(status="partial", readiness_kind="delivery_prepared_pending_gate",
        reason="Five exact CPU rail delivery paths prepared; original required-stop authority, Native crossing/gate/marked-lane source, actual pixels, physical completion and legal judgment remain pending.",
        counts={"source_topics": 2, "selected_comparison_cases_planned": 5,
            "delivery_cases_prepared": 5, "candidates_proven": 10,
            "comparisons_planned": 4, "accepted_membership_rows": 0,
            "accepted_equivalence_reuses": 0},
        current_cpu_proof={"format": "c202463-selected-cpu-delivery-proof-v1",
            "manifest_sha256": sha(manifest_path),
            "semantic_index_sha256": sha(HERE / "proposals/semantic-index.json"),
            "selected_cases": selected_proofs, "native_executed": False,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False},
        tests=tests, candidate_plans_proven=10, cases_selected=5,
        comparison_audits_passed=4, carla_executed=False, recordings_accepted=0,
        first_gpu_delivery_command=f"C202463_RAIL_REVIEW_DIR=$RAIL_REVIEW_DIR PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange execute-delivery --repo . --batch full-train-delivery --db $DB --assignment {ASSIGNMENT} --case {manifest['cases'][0]['case_id']} --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT")
    write(result_path, result)
    print(json.dumps({"manifest_sha256": sha(manifest_path),
                      "result_sha256": sha(result_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
