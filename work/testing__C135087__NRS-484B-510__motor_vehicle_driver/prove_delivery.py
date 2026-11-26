"""Pin positive diagnostic and original-mode rejection for selected cases."""

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
PYTHON = str(REPO / ".venv-cpu/bin/python")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    data = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work/c135087-runtime-output"))
    for entry in data["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        attempt = REPO / ".runtime-work/c135087-saved-v2" / ("saved-" + suffix) / "v0001/analysis"
        base = [PYTHON, str(ROOT / "selected_delivery.py"), "--attempt", str(attempt),
                "--case", case]
        positive = base + ["--allow-diagnostic"]
        passed = subprocess.run(positive, cwd=REPO, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        positive_log = ROOT / ("cpu-selected-" + suffix + ".log")
        positive_log.write_text(passed.stdout.rstrip() + "\n")
        if passed.returncode:
            raise ValueError("selected diagnostic failed: " + passed.stdout[-1000:])
        rejected = subprocess.run(base, cwd=REPO, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        negative_log = ROOT / ("cpu-selected-negative-" + suffix + ".log")
        negative_log.write_text(rejected.stdout.rstrip() + "\n")
        expected = "synthetic saved source cannot satisfy original delivery"
        if rejected.returncode == 0 or expected not in rejected.stdout:
            raise ValueError("synthetic attempt accepted as original")
        entry["delivery_acceptance"] = {"case_id": case, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "selected_delivery.py", "script_sha256": sha(ROOT / "selected_delivery.py"),
            "command": " ".join(positive), "test_exit_code": 0,
            "test_log": positive_log.name, "test_log_sha256": sha(positive_log),
            "negative_command": " ".join(base), "negative_exit_code": rejected.returncode,
            "negative_expected_error": expected, "negative_log": negative_log.name,
            "negative_log_sha256": sha(negative_log), "diagnostic_fixture": True,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
        print(suffix + " selected delivery proof passed", flush=True)
    MANIFEST.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
