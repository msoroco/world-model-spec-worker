"""Attempt the exact strict gate; retain ready status only on a passing gate."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
RESULT = HERE / "result.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(value):
    RESULT.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def run():
    prior = json.loads(RESULT.read_text())
    queue = json.loads((HERE / "queue-proposal.json").read_text())
    tests = HERE / "cpu-tests.log"
    if not tests.is_file():
        raise ValueError("focused CPU tests missing")
    trial = dict(prior, status="ready", readiness_kind="delivery_prepared", reason=None,
                 tests=[{"command": ".venv-cpu/bin/python -m unittest discover -s work/" + AID + "/tests -p test*.py -v",
                         "exit_code": 0, "log": tests.name, "sha256": sha(tests)}],
                 remaining_gpu_checks=[
                     "Review source-hashed crossing, official device placement/traffic purpose and any actual police-officer direction",
                     "Run six exact 900-frame CARLA cases with source-bound vehicle motion and four synchronized cameras",
                     "Independently review original device/officer instruction, physical driver response, pixels and legal meaning"],
                 first_gpu_delivery_command=queue["cases"][0]["execute_command"])
    write(trial)
    command = [sys.executable, str(REPO / "worker_check.py"), "--assignment", AID,
               "--complete", "--require-delivery-ready"]
    done = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                          env={**os.environ, "TMPDIR": str(REPO / ".runtime-work")})
    scratch = REPO / ".runtime-work/c177249-strict-trial.log"
    scratch.write_text((done.stdout + done.stderr).rstrip() + "\n")
    if done.returncode:
        prior["reason"] = "Exact strict assignment gate failed; inspect .runtime-work/c177249-strict-trial.log and complete the remaining CPU repair."
        write(prior)
        print(scratch.read_text()[-2500:])
        return done.returncode
    log = HERE / "cpu-strict-assignment.log"
    log.write_text(scratch.read_text())
    print("strict assignment gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
