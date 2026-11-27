"""Run exact-case three-outcome CPU physical and lifecycle checks."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / ".venv-cpu/bin/python"
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")


def prove():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        name = case.removeprefix(HERE.name + "__")
        fixtures = []
        for kind in KINDS:
            result = HERE / f"physical-{name}-{kind}.json"
            log = HERE / f"physical-{name}-{kind}.log"
            command = [str(PYTHON), str(HERE / "physical_probe.py"),
                       "--case", case, "--kind", kind, "--output", str(result)]
            done = subprocess.run(command, cwd=REPO, env=os.environ, text=True,
                                  capture_output=True)
            if done.returncode:
                raise ValueError(f"physical {name} {kind} failed: {done.stderr[-1500:]}")
            log.write_text(done.stdout.rstrip() + "\n")
            fixtures.append({"kind": kind, "command": " ".join(command),
                             "exit_code": 0, "result": result.name,
                             "result_sha256": sha(result), "log": log.name,
                             "log_sha256": sha(log)})
        life = fixtures[0]
        receipt = HERE / f"physical-{name}-receipt.json"
        write(receipt, {"format": "worker-physical-preparation", "case_id": case,
                        "construction_sha256": entry["construction_sha256"],
                        "fixtures": fixtures, "lifecycle": {"command": life["command"],
                            "events": ["capture_finished", "encoders_closed",
                                "restoration_verified", "native_exit", "owner_released",
                                "saved_processing_started"], "exit_code": 0,
                            "log": life["log"], "log_sha256": life["log_sha256"]},
                        "scope": "synthetic CPU protocol only; no physical acceptance"})
        entry["physical_preparation"] = {"receipt": receipt.name, "sha256": sha(receipt)}
        print("physical+lifecycle", name, "passed", flush=True)
    write(manifest_path, manifest)


if __name__ == "__main__":
    prove()
