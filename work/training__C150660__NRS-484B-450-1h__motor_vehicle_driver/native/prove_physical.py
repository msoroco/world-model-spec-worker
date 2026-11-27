"""Retain three synthetic physical outcomes and ownership lifecycle proof."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from case_specs import CASES

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv-cpu/bin/python"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for suffix in CASES:
    case = FOLDER.name + "__" + suffix
    path = FOLDER / "physical-proof" / suffix
    path.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        output = path / (kind + ".json")
        log = path / (kind + ".log")
        command = [str(PYTHON), str(FOLDER / "physical_preparation.py"),
                   "--case", case, "--kind", kind, "--output", str(output)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        log.write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(kind + ": " + result.stderr)
        fixtures.append({"kind": kind, "command": " ".join(command), "exit_code": 0,
                         "log": str(log.relative_to(FOLDER)), "log_sha256": sha(log),
                         "result": str(output.relative_to(FOLDER)),
                         "result_sha256": sha(output)})
    output = path / "lifecycle.json"
    log = path / "lifecycle.log"
    command = [str(PYTHON), str(FOLDER / "physical_preparation.py"),
               "--case", case, "--kind", "lifecycle", "--output", str(output)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("lifecycle: " + result.stderr)
    life = json.loads(output.read_text())
    life.update({"log": str(log.relative_to(FOLDER)), "log_sha256": sha(log)})
    construction = FOLDER / "cases" / suffix / "primary/construction.json"
    proof = {"format": "c150660-safety-zone-physical-cpu-v1", "case_id": case,
             "construction_sha256": sha(construction), "fixtures": fixtures,
             "lifecycle": life, "diagnostic_only": True,
             "original_native_observed": False}
    receipt = path / "proof.json"
    receipt.write_text(json.dumps(proof, indent=2) + "\n")
    print(suffix, sha(receipt))
