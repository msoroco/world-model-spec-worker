"""Rebuild the exact CPU receipts after a Native construction source change."""
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
RUN = REPO / ".runtime-work/c416422-nov27-capture-v4"
PYTHON = REPO / ".venv-cpu/bin/python"
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"
CASES = ("prompt_brake", "deferred_brake")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def log_text(value):
    lines = [line.rstrip() for line in value.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + ("\n" if lines else "")


def command(args):
    return (f'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/{RUN.relative_to(REPO)}" '
            "PYTHONDONTWRITEBYTECODE=1 " + shlex.join(str(x) for x in args))


def run(args, log=None, expected=0, more_env=None):
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(RUN),
               PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(RUN / "tmp"),
               MPLCONFIGDIR=str(RUN / "mpl"))
    env.update(more_env or {})
    result = subprocess.run([str(x) for x in args], cwd=REPO, env=env,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if log:
        (ROOT / log).write_text(log_text(result.stdout))
    if result.returncode != expected:
        raise RuntimeError(f"{command(args)} exited {result.returncode}: {result.stdout[-1800:]}")
    return result.stdout


def main():
    RUN.mkdir(parents=True, exist_ok=False)
    (RUN / "tmp").mkdir()
    (RUN / "mpl").mkdir()
    if not VALIDATOR.is_file():
        raise FileNotFoundError(VALIDATOR)
    for author in ("diagnostic_author.py", "construction_author.py", "fallback_author.py"):
        run([PYTHON, ROOT / author])
    run([PYTHON, "-m", "unittest", "discover", "-s", ROOT / "tests", "-v"],
        "cpu-tests.log")
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        for candidate in ("primary", "fallback1"):
            selected = entry if candidate == "primary" else entry["candidates"][0]
            args = [PYTHON, "runtime.py", "offline", "--manifest", MANIFEST,
                    "--case", case, "--candidate", candidate, "--output",
                    RUN / f"offline-{suffix}-{candidate}"]
            run(args)
            offline_log = ROOT / f"proof-{suffix}-{candidate}.log"
            offline_log.write_text(log_text((RUN / f"offline-{suffix}-{candidate}" / "offline.log").read_text()))
            selected["offline"] = {"command": command(args),
                                   "construction_sha256": selected["construction_sha256"],
                                   "exit_code": 0, "log": offline_log.name,
                                   "log_sha256": sha(offline_log)}
            args = [PYTHON, "runtime.py", "compatibility", "--manifest", MANIFEST,
                    "--case", case, "--candidate", candidate, "--output",
                    RUN / f"compat-{suffix}-{candidate}", "--library", REPO / "runtime/library",
                    "--validator", VALIDATOR]
            run(args)
            output = RUN / f"compat-{suffix}-{candidate}"
            prefix = f"compat-{suffix}-{candidate}"
            for source, target in (("compatibility-analysis.log", f"{prefix}-analysis.log"),
                                   ("negative-analysis.log", f"{prefix}-negative.log"),
                                   ("compatibility.json", f"{prefix}-receipt.json")):
                shutil.copyfile(output / source, ROOT / target)
            selected["compatibility"] = {"command": command(args),
                                          "log": f"{prefix}-analysis.log",
                                          "negative_log": f"{prefix}-negative.log",
                                          "receipt": f"{prefix}-receipt.json",
                                          "sha256": sha(ROOT / f"{prefix}-receipt.json")}
            if candidate == "primary":
                entry["negative"] = {"log": f"{prefix}-negative.log"}
        args = [PYTHON, ROOT / "physical_probe.py", "--case", case,
                "--output", RUN / f"physical-{suffix}"]
        run(args, f"physical-{suffix}-probe.log",
            more_env={"PYTHONPATH": str(REPO / "runtime/scenario_pipeline")})
        physical = {"construction_sha256": entry["construction_sha256"],
                    "fixtures": [], "lifecycle": {
                        "events": ["capture_finished", "encoders_closed", "restoration_verified",
                                   "native_exit", "owner_released", "saved_processing_started"],
                        "exit_code": 0, "log": f"physical-{suffix}-probe.log",
                        "log_sha256": sha(ROOT / f"physical-{suffix}-probe.log")},
                    "scope": "Synthetic roadside approach progression and lifecycle protocol; no Native capture or legal acceptance"}
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result = f"physical-{suffix}-{kind}.json"
            physical["fixtures"].append({"kind": kind, "command": command(args),
                                         "exit_code": 0, "log": f"physical-{suffix}-probe.log",
                                         "log_sha256": sha(ROOT / f"physical-{suffix}-probe.log"),
                                         "result": result, "result_sha256": sha(ROOT / result)})
        receipt_path = ROOT / f"physical-{suffix}-proof.json"
        write(receipt_path, physical)
        entry["physical_preparation"] = {"receipt": receipt_path.name, "sha256": sha(receipt_path)}
        positive = [PYTHON, ROOT / "audit_probe.py", "--case", case,
                    "--output", RUN / f"audit-{suffix}-positive"]
        negative = [PYTHON, ROOT / "audit_probe.py", "--case", case,
                    "--output", RUN / f"audit-{suffix}-negative", "--negative"]
        audit = json.loads(run(positive, f"audit-{suffix}-positive.log",
                               more_env={"PYTHONPATH": str(ROOT) + ":" + str(REPO / "runtime/scenario_pipeline")}))
        write(RUN / f"audit-{suffix}.json", audit)
        run(negative, f"audit-{suffix}-negative.log", expected=1,
            more_env={"PYTHONPATH": str(ROOT) + ":" + str(REPO / "runtime/scenario_pipeline")})
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(ROOT / "delivery_audit.py"),
            "command": command(positive), "test_exit_code": 0,
            "test_log": f"audit-{suffix}-positive.log",
            "test_log_sha256": sha(ROOT / f"audit-{suffix}-positive.log"),
            "negative_command": command(negative), "negative_exit_code": 1,
            "negative_expected_error": "sealed original missing or changed",
            "negative_log": f"audit-{suffix}-negative.log",
            "negative_log_sha256": sha(ROOT / f"audit-{suffix}-negative.log")}
    write(MANIFEST, manifest)
    run([PYTHON, ROOT / "refresh_saved.py"], more_env={"C416422_RUN_ROOT": str(RUN)})
    prompt = RUN / "audit-prompt_brake.json"
    deferred = RUN / "audit-deferred_brake.json"
    args = [PYTHON, ROOT / "comparison_audit.py", prompt, deferred]
    run(args, "comparison-positive.log")
    wrong = json.loads(deferred.read_text())
    wrong["map_sha256"] = "wrong original map"
    write(RUN / "audit-deferred_brake-wrong.json", wrong)
    negative = [PYTHON, ROOT / "comparison_audit.py", prompt,
                RUN / "audit-deferred_brake-wrong.json"]
    run(negative, "comparison-negative.log", expected=1)
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["comparison_proofs"] = [{"comparison_id": "near_road_response_timing",
                                  "receipt": "comparison-positive.log",
                                  "sha256": sha(ROOT / "comparison-positive.log"),
                                  "negative_log": "comparison-negative.log",
                                  "negative_log_sha256": sha(ROOT / "comparison-negative.log")}]
    write(plan_path, plan)
    semantic = [PYTHON, ROOT / "semantic_check.py"]
    run(semantic, "semantic-stage-check.log",
        more_env={"PYTHONPATH": str(REPO / "runtime/scenario_pipeline") + ":" + str(REPO / "runtime/python")})
    result_path = ROOT / "result.json"
    result = json.loads(result_path.read_text())
    test_cmd = [PYTHON, "-m", "unittest", "discover", "-s", ROOT / "tests", "-v"]
    result["tests"] = [{"command": command(test_cmd), "exit_code": 0,
                        "log": "cpu-tests.log", "sha256": sha(ROOT / "cpu-tests.log")},
                       {"command": command(semantic), "exit_code": 0,
                        "log": "semantic-stage-check.log",
                        "sha256": sha(ROOT / "semantic-stage-check.log")}]
    write(result_path, result)
    print("refreshed both primary and fallback exact cases, saved processing, audits, and 16 tests")


if __name__ == "__main__":
    main()
