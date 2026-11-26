"""Rebind diagnostic saved-only and independent selected delivery checks."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c136559-600-1c"
MANIFEST = ROOT / "execution-manifest.json"
PYTHON = str(REPO / ".venv-cpu/bin/python")
VALIDATOR = REPO / ".runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, env, log, expected=0):
    result = subprocess.run(args, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(result.stdout.rstrip() + "\n")
    if result.returncode != expected:
        raise ValueError("unexpected exit: " + " ".join(args) + "\n" + result.stdout[-1600:])
    return result.stdout


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               TMPDIR=str(SCRATCH / "tmp"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "output"))
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        attempt = SCRATCH / ("saved-attempt-" + suffix + "-v2")
        saved = SCRATCH / ("saved-" + suffix + "-v2")
        run([PYTHON, "runtime.py", "materialize", "--manifest", str(MANIFEST),
             "--case", case, "--output", str(attempt)], env,
            ROOT / ("cpu-materialize-" + suffix + "-v2.log"))
        source = SCRATCH / ("saved-source-" + suffix)
        for path in source.iterdir():
            target = attempt / path.name
            if target.exists():
                raise ValueError("fixture shadows selected construction: " + str(target))
            if path.is_dir():
                shutil.copytree(path, target)
            else:
                shutil.copy2(path, target)
        saved_log = ROOT / ("cpu-saved-" + suffix + "-v2.log")
        args = [PYTHON, "runtime.py", "process-saved", "--manifest", str(MANIFEST),
                "--case", case, "--attempt", str(attempt), "--output", str(saved),
                "--library", str(REPO / "runtime/library"),
                "--validator", str(VALIDATOR)]
        run(args, env, saved_log)
        receipt_path = ROOT / ("cpu-saved-" + suffix + "-v2.json")
        shutil.copy2(saved / "v0001/processing.json", receipt_path)
        analysis = saved / "v0001/analysis"
        selected_log = ROOT / ("cpu-selected-" + suffix + "-v2.log")
        negative_log = ROOT / ("cpu-selected-negative-" + suffix + "-v2.log")
        positive = [PYTHON, str(ROOT / "selected_delivery.py"), "--attempt", str(analysis),
                    "--case", case, "--allow-diagnostic"]
        negative = positive[:-1]
        run(positive, env, selected_log)
        negative_result = subprocess.run(negative, cwd=REPO, env=env, text=True,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        negative_log.write_text(negative_result.stdout.rstrip() + "\n")
        if negative_result.returncode == 0 or "synthetic saved source cannot satisfy original delivery" not in negative_result.stdout:
            raise ValueError("diagnostic source accepted as original: " + case)
        entry["saved_diagnostic"] = {"receipt": receipt_path.name,
                                      "sha256": sha(receipt_path),
                                      "source": str(source.relative_to(REPO)),
                                      "physical_acceptance_claimed": False}
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["demo-test", "full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "selected_delivery.py", "script_sha256": sha(ROOT / "selected_delivery.py"),
            "command": " ".join(positive), "test_exit_code": 0,
            "test_log": selected_log.name, "test_log_sha256": sha(selected_log),
            "negative_command": " ".join(negative),
            "negative_exit_code": negative_result.returncode,
            "negative_expected_error": "synthetic saved source cannot satisfy original delivery",
            "negative_log": negative_log.name,
            "negative_log_sha256": sha(negative_log),
            "diagnostic_fixture": True,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
        print(suffix + " saved/delivery passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
