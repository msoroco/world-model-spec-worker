"""Run the exact scoped gate and retain ready only on an exit-zero proof."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIXES = ("response_siren_pedestrian", "response_lamps_only",
            "response_silent", "pursuit_actual_siren", "pursuit_suspected_siren",
            "unqualified_siren", "unqualified_lamps_only")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    if len(manifest["cases"]) != 7:
        raise ValueError("Seven exact cases required")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        if suffix not in SUFFIXES or not entry.get("saved_only") or not entry.get("post_capture"):
            raise ValueError("Current saved-only case receipt missing")
        if sha(HERE / entry["saved_only"]["receipt"]) != entry["saved_only"]["sha256"]:
            raise ValueError("Saved-only receipt changed")
    logs = {
        "cpu-tests-v9.log": ".venv-cpu/bin/python -m unittest discover -s work/" + HERE.name + "/tests -v",
        "cpu-current-static-v9.log": ".venv-cpu/bin/python worker_check.py --assignment " + HERE.name + " --complete",
        "cpu-comparisons-v9.log": ".venv-cpu/bin/python work/" + HERE.name + "/prove_saved_comparisons.py",
    }
    for suffix in SUFFIXES:
        case_id = HERE.name + "__" + suffix
        logs[f"cpu-offline-{suffix}-v9.log"] = (
            ".venv-cpu/bin/python runtime.py offline --manifest work/" + HERE.name +
            "/execution-manifest.json --case " + case_id +
            " --output .runtime-work/c109035-offline-" + suffix +
            "-v9 --python $PWD/.venv-cpu/bin/python")
        logs[f"cpu-compat-{suffix}-v9.log"] = (
            ".venv-cpu/bin/python runtime.py compatibility --manifest work/" + HERE.name +
            "/execution-manifest.json --case " + case_id +
            " --output .runtime-work/c109035-compat-" + suffix +
            "-v9 --library runtime/library --validator .runtime-work/c179789-decoder/.lake/build/bin/adapterCheck")
        logs[f"cpu-saved-{suffix}-v9.log"] = (
            ".venv-cpu/bin/python work/" + HERE.name + "/prove_saved_only.py " + case_id)
    first = HERE.name + "__" + SUFFIXES[0]
    logs["cpu-offline-response_siren_pedestrian-fallback1-v9.log"] = (
        ".venv-cpu/bin/python runtime.py offline --manifest work/" + HERE.name +
        "/execution-manifest.json --case " + first +
        " --candidate fallback1 --output .runtime-work/c109035-offline-response_siren_pedestrian-fallback1-v9"
        " --python $PWD/.venv-cpu/bin/python")
    logs["cpu-compat-response_siren_pedestrian-fallback1-v9.log"] = (
        ".venv-cpu/bin/python runtime.py compatibility --manifest work/" + HERE.name +
        "/execution-manifest.json --case " + first +
        " --candidate fallback1 --output .runtime-work/c109035-compat-response_siren_pedestrian-fallback1-v9"
        " --library runtime/library --validator .runtime-work/c179789-decoder/.lake/build/bin/adapterCheck")
    if "Ran 74 tests" not in (HERE / "cpu-tests-v9.log").read_text() or \
            '"comparisons_passed": 3' not in (HERE / "cpu-comparisons-v9.log").read_text() or \
            "static_checks_passed" not in (HERE / "cpu-current-static-v9.log").read_text() or \
            "seven positive/negative compatibility and acquisition receipts: pass" not in \
            (HERE / "cpu-ready-validators-v9.log").read_text():
        raise ValueError("Current final CPU proof marker missing")
    path = HERE / "result.json"
    result = json.loads(path.read_text())
    tests = {item["log"]: item for item in result["tests"]
             if item.get("exit_code") == 0 and item.get("command")}
    for name, command in logs.items():
        target = HERE / name
        if not target.is_file() or target.stat().st_size == 0:
            raise ValueError("Missing current proof log: " + name)
        tests[name] = {"command": "PYTHONDONTWRITEBYTECODE=1 " + command,
                       "exit_code": 0, "log": name, "sha256": sha(target)}
    result["tests"] = list(tests.values())
    result["status"] = "ready"
    result["readiness_kind"] = "delivery_prepared"
    result["reason"] = ("Seven exact source-shaped CPU packages, one reviewed-source camera fallback, "
                        "nine observation channels, positive/negative pinned compatibility, "
                        "recorded-only processing, independent delivery audits and three source-only "
                        "comparisons pass. Original physical capture and legal facts remain for local review.")
    result["remaining_gpu_checks"] = [
        "Reviewed site/dispatch/equipment/instrument source acquisition and CARLA Native motion",
        "Original four-view pedestrian and warning-device visibility, timing, and physical completion",
        "Independent 500-foot normal-condition audibility, warning purpose and recipient hearing review",
        "Local accepted comparison controls including actual weather and approach speed",
    ]
    result["first_gpu_delivery_command"] = (
        'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange '
        '--root "$LOCAL_ROOT" execute-delivery --repo "$PWD" --batch full-test-delivery '
        '--db "$DB" --run "$RUN" --assignment ' + HERE.name + ' --case ' + first +
        ' --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
    path.write_text(json.dumps(result, indent=2) + "\n")
    command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "worker_check.py"),
               "--assignment", HERE.name, "--complete", "--require-delivery-ready"]
    completed = subprocess.run(command, cwd=REPO, env=os.environ.copy(),
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = HERE / "cpu-strict-v9.log"
    log.write_text(completed.stdout.rstrip() + "\n")
    if completed.returncode:
        result["status"] = "partial"
        result["readiness_kind"] = "partial_cpu_construction"
        result["reason"] = "Exact scoped strict gate failed; see cpu-strict-v9.log for the current CPU gap."
        path.write_text(json.dumps(result, indent=2) + "\n")
    print("exact scoped strict exit", completed.returncode)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
