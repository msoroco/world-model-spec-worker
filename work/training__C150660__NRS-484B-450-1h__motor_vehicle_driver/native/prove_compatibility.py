"""Run pinned public selected compatibility and missing-source negative per case."""

import concurrent.futures
import hashlib
import json
import os
import subprocess
from pathlib import Path

from case_specs import CASES

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv-cpu/bin/python"
SCRATCH = ROOT / ".runtime-work/c150660-compat-v2"
TMP = ROOT / ".runtime-work/c150660-tmp"
VALIDATOR = ROOT / ".runtime-work/c150660-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proof(suffix, candidate):
    output = SCRATCH / suffix / candidate
    if not (output / "compatibility.json").exists():
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [str(PYTHON), str(ROOT / "runtime.py"), "compatibility",
                   "--manifest", str(FOLDER / "draft-construction-manifest.json"),
                   "--case", FOLDER.name + "__" + suffix,
                   "--output", str(output), "--library", str(ROOT / "runtime/library"),
                   "--validator", str(VALIDATOR)]
        if candidate != "primary":
            command += ["--candidate", candidate]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                   env={**os.environ, "TMPDIR": str(TMP),
                                        "PYTHONDONTWRITEBYTECODE": "1"})
        if completed.returncode:
            raise RuntimeError(suffix + " " + candidate + ": " +
                               completed.stderr[-3500:])
    receipt = json.loads((output / "compatibility.json").read_text())
    if not receipt.get("passed") or receipt["case_id"] != FOLDER.name + "__" + suffix:
        raise RuntimeError("Invalid selected compatibility: " + suffix + " " + candidate)
    destination = FOLDER / "compatibility" / suffix / candidate
    destination.mkdir(parents=True, exist_ok=True)
    for source, name in (("compatibility.json", "compatibility.json"),
                         ("compatibility-analysis.log", "analysis.log"),
                         ("negative-analysis.log", "negative.log")):
        (destination / name).write_bytes((output / source).read_bytes())
    return suffix, candidate, sha(destination / "compatibility.json")


if __name__ == "__main__":
    SCRATCH.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    jobs = [(suffix, candidate) for suffix in CASES for candidate in ("primary", "fallback1")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(proof, *job) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            print(*future.result(), flush=True)
