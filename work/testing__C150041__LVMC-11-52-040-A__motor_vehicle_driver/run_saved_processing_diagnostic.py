"""Run pinned saved-only processing against six passed synthetic attempts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from parking_pose import REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
VALIDATOR = REPO / ".runtime-work/c150041-decoder-v1/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(kind):
    case = ROOT.name + "__" + kind
    source = REPO / ".runtime-work" / ("c150041-compat-v8-" + kind)
    destination = REPO / ".runtime-work" / ("c150041-process-saved-v3-" + kind)
    command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
               "process-saved", "--manifest", str(ROOT / "cpu-compatibility-manifest.json"),
               "--case", case, "--attempt", str(source), "--output", str(destination),
               "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                            timeout=300)
    folder = ROOT / "diagnostic" / kind
    log = folder / "cpu-process-saved.log"
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(kind + " saved processing failed; see cpu-process-saved.log")
    version = destination / "v0001"
    receipt = json.loads((version / "processing.json").read_text())
    if receipt.get("passed") is not True or receipt.get("missing_evidence") is not False:
        raise ValueError("synthetic saved processing incomplete")
    for name in ("processing.json", "analysis.log", "final-decode.json"):
        shutil.copyfile(version / name, folder / ("cpu-process-saved-" + name))
    return {"case_id": case, "passed": True, "receipt_sha256": sha(folder / "cpu-process-saved-processing.json"),
            "log_sha256": sha(log)}


if __name__ == "__main__":
    for suffix in REQUESTS:
        print(json.dumps(run(suffix)), flush=True)
