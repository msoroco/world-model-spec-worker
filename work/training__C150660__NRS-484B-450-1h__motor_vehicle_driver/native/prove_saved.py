"""Run selected saved-only processing on source-complete CPU fixtures."""

import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from case_specs import CASES

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv-cpu/bin/python"
COMPAT = ROOT / ".runtime-work/c150660-compat-v3"
SAVED = ROOT / ".runtime-work/c150660-saved-v3"
TMP = ROOT / ".runtime-work/c150660-tmp"
VALIDATOR = ROOT / ".runtime-work/c150660-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(suffix):
    case = FOLDER.name + "__" + suffix
    attempt = COMPAT / suffix / "primary"
    for _ in range(600):
        if (attempt / "compatibility.json").is_file():
            break
        time.sleep(2)
    else:
        raise TimeoutError("Selected compatibility not available: " + suffix)
    output = SAVED / suffix
    receipt = output / "v0001/processing.json"
    stdout = SAVED / (suffix + ".stdout")
    if not receipt.is_file():
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [str(PYTHON), str(ROOT / "runtime.py"), "process-saved",
                   "--manifest", str(FOLDER / "draft-construction-manifest.json"),
                   "--case", case, "--attempt", str(attempt), "--output", str(output),
                   "--library", str(ROOT / "runtime/library"),
                   "--validator", str(VALIDATOR)]
        with stdout.open("wb") as log:
            process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                     env={**os.environ, "TMPDIR": str(TMP),
                                          "PYTHONDONTWRITEBYTECODE": "1"})
        if process.returncode:
            raise RuntimeError("Saved-only processing failed: " + suffix + " " +
                               stdout.read_text()[-2400:])
    else:
        if not stdout.is_file():
            shutil.copyfile(ROOT / ".runtime-work/c150660-saved-first.stdout", stdout)
    proof = json.loads(receipt.read_text())
    construction = FOLDER / "cases" / suffix / "primary/construction.json"
    if (not proof.get("passed") or not proof.get("recorded_only") or
            proof.get("missing_evidence") or not proof.get("originals_preserved") or
            proof["analysis_revision"]["construction_sha256"] != sha(construction)):
        raise ValueError("Saved-only receipt stale/incomplete: " + suffix)
    destination = FOLDER / "saved"
    destination.mkdir(exist_ok=True)
    shutil.copyfile(receipt, destination / (suffix + "-processing.json"))
    shutil.copyfile(stdout, destination / (suffix + "-processing.log"))
    return suffix, sha(destination / (suffix + "-processing.json"))


if __name__ == "__main__":
    SAVED.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run_case, suffix) for suffix in CASES]
        for future in concurrent.futures.as_completed(futures):
            print(*future.result(), flush=True)
