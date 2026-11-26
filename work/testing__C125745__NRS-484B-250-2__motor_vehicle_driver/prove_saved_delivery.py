"""Test recorded-only processing and independent diagnostic/original distinction."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c125745-250-2"
MANIFEST = ROOT / "execution-manifest.json"
PYTHON = str(REPO / ".venv-cpu/bin/python")
VALIDATOR = str(REPO / ".runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck")


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
        source = SCRATCH / ("fixture-" + suffix + "-v6")
        attempt = SCRATCH / ("saved-attempt-" + suffix + "-v6")
        saved = SCRATCH / ("saved-" + suffix + "-v6")
        run([PYTHON, "runtime.py", "fixture", "--recipe",
             str(ROOT / ("diagnostic-" + suffix + "-recipe.json")),
             "--output", str(source)], env,
            ROOT / ("cpu-fixture-" + suffix + "-v6.log"))
        run([PYTHON, "runtime.py", "materialize", "--manifest", str(MANIFEST),
             "--case", case, "--output", str(attempt)], env,
            ROOT / ("cpu-materialize-" + suffix + "-v6.log"))
        for path in source.iterdir():
            target = attempt / path.name
            if target.exists():
                raise ValueError("diagnostic fixture shadows selected construction")
            if path.is_dir():
                shutil.copytree(path, target)
            else:
                shutil.copy2(path, target)
        saved_log = ROOT / ("cpu-saved-" + suffix + "-v6.log")
        saved_command = [PYTHON, "runtime.py", "process-saved",
                         "--manifest", str(MANIFEST), "--case", case,
                         "--attempt", str(attempt), "--output", str(saved),
                         "--library", str(REPO / "runtime/library"),
                         "--validator", VALIDATOR]
        run(saved_command, env, saved_log)
        receipt = ROOT / ("cpu-saved-" + suffix + "-v6.json")
        shutil.copy2(saved / "v0001/processing.json", receipt)
        analysis = saved / "v0001/analysis"
        positive = [PYTHON, str(ROOT / "selected_delivery.py"),
                    "--attempt", str(analysis), "--case", case,
                    "--allow-diagnostic"]
        negative = positive[:-1]
        positive_log = ROOT / ("cpu-selected-" + suffix + "-v6.log")
        negative_log = ROOT / ("cpu-selected-negative-" + suffix + "-v6.log")
        run(positive, env, positive_log)
        rejection = subprocess.run(negative, cwd=REPO, env=env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        negative_log.write_text(rejection.stdout.rstrip() + "\n")
        expected_error = "synthetic saved source cannot satisfy original delivery"
        if rejection.returncode == 0 or expected_error not in rejection.stdout:
            raise ValueError("synthetic timing source accepted as original")
        entry["saved_diagnostic"] = {"receipt": receipt.name, "sha256": sha(receipt),
                                      "source": str(source.relative_to(REPO)),
                                      "physical_acceptance_claimed": False}
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "selected_delivery.py", "script_sha256": sha(ROOT / "selected_delivery.py"),
            "command": " ".join(positive), "test_exit_code": 0,
            "test_log": positive_log.name, "test_log_sha256": sha(positive_log),
            "negative_command": " ".join(negative),
            "negative_exit_code": rejection.returncode,
            "negative_expected_error": expected_error,
            "negative_log": negative_log.name,
            "negative_log_sha256": sha(negative_log),
            "diagnostic_fixture": True,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
        entry["post_capture"] = {"recorded_only": True,
                                 "command": " ".join(saved_command),
                                 "feedback_command": "inspect " + str(saved / "v0001/feedback.json"),
                                 "test_exit_code": 0, "test_log": saved_log.name,
                                 "test_log_sha256": sha(saved_log)}
        print(suffix + " saved/delivery passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
