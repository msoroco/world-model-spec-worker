"""Bind exact CPU physical and capture lifecycle fixtures for each rail case."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parents[1]
MANIFEST = WORK / "execution-manifest.json"
SCRIPT = WORK / "native/physical_fixture.py"
PYTHON = ROOT / ".venv-cpu/bin/python"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(ROOT / ".runtime-work"))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        folder = WORK / "physical-proofs" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            output = folder / (kind + ".json")
            log = folder / (kind + ".log")
            command = [str(PYTHON), "-B", str(SCRIPT), "--condition", suffix,
                       "--kind", kind, "--output", str(output)]
            run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            log.write_text(run.stdout + run.stderr)
            if run.returncode:
                raise RuntimeError("Physical fixture failed: " + suffix + "/" + kind + ": " + log.read_text())
            fixtures.append({"kind": kind, "command": " ".join(command), "exit_code": 0,
                             "log": str(log.relative_to(WORK)), "log_sha256": sha(log),
                             "result": str(output.relative_to(WORK)), "result_sha256": sha(output)})
        lifecycle_path = folder / "lifecycle.json"
        lifecycle_log = folder / "lifecycle.log"
        command = [str(PYTHON), "-B", str(SCRIPT), "--condition", suffix,
                   "--kind", "lifecycle", "--output", str(lifecycle_path)]
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        lifecycle_log.write_text(run.stdout + run.stderr)
        if run.returncode:
            raise RuntimeError("Lifecycle fixture failed: " + suffix)
        proof = {"format": "lvmc-cpu-physical-preparation-v1", "case_id": entry["case_id"],
                 "construction_sha256": entry["construction_sha256"], "fixtures": fixtures,
                 "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                          "restoration_verified", "native_exit",
                                          "owner_released", "saved_processing_started"],
                               "exit_code": 0, "log": str(lifecycle_log.relative_to(WORK)),
                               "log_sha256": sha(lifecycle_log)},
                 "original_native_executed": False, "physical_completion_claimed": False}
        proof_path = folder / "proof.json"
        proof_path.write_text(json.dumps(proof, indent=2) + "\n")
        entry["physical_preparation"] = {"receipt": str(proof_path.relative_to(WORK)),
                                          "sha256": sha(proof_path)}
        print("PASS physical", suffix, flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    build()
