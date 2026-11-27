"""Run three outcome fixtures and Native closure for every exact approach case."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = str(REPO / ".venv-cpu/bin/python")
MANIFEST = HERE / "execution-manifest.json"
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def prove():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        name = entry["case_id"].removeprefix(HERE.name + "__")
        fixtures = []
        complete = None
        for kind in KINDS:
            output = HERE / ("physical-" + name + "-" + kind + ".json")
            command = [PYTHON, str(HERE / "physical_probe.py"), "--case",
                       entry["case_id"], "--kind", kind, "--output", str(output)]
            done = subprocess.run(command, cwd=REPO, env=os.environ,
                                  capture_output=True, text=True)
            log = HERE / ("physical-" + name + "-" + kind + ".log")
            log.write_text((done.stdout + done.stderr).rstrip() + "\n")
            if done.returncode:
                raise RuntimeError("physical signal proof failed: " + log.read_text()[-1500:])
            fixture = {"command": " ".join(command), "exit_code": 0,
                       "kind": kind, "log": log.name, "log_sha256": sha(log),
                       "result": output.name, "result_sha256": sha(output)}
            fixtures.append(fixture)
            if kind == "complete_motion":
                complete = fixture
        receipt = {"format": "worker-physical-preparation",
                   "case_id": entry["case_id"],
                   "construction_sha256": entry["construction_sha256"],
                   "fixtures": fixtures, "scope": "synthetic CPU protocol only; no physical acceptance",
                   "lifecycle": {"command": complete["command"],
                                 "events": ["capture_finished", "encoders_closed",
                                            "restoration_verified", "native_exit",
                                            "owner_released", "saved_processing_started"],
                                 "exit_code": 0, "log": complete["log"],
                                 "log_sha256": complete["log_sha256"]}}
        path = HERE / ("physical-" + name + "-receipt.json")
        write(path, receipt)
        entry["physical_preparation"] = {"receipt": path.name, "sha256": sha(path)}
        print("physical+lifecycle", name, "passed", flush=True)
    write(MANIFEST, manifest)


if __name__ == "__main__":
    prove()
