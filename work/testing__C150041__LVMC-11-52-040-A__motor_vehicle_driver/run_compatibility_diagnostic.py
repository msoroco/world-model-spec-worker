"""Run pinned positive/negative saved compatibility on six synthetic cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from parking_pose import REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "cpu-compatibility-manifest.json"
VALIDATOR = REPO / ".runtime-work/c150041-decoder-v1/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(kind):
    case = ROOT.name + "__" + kind
    output = REPO / ".runtime-work" / ("c150041-compat-v10-" + kind)
    if output.exists():
        raise ValueError("retain prior compatibility attempt: " + str(output))
    command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
               "compatibility", "--manifest", str(MANIFEST), "--case", case,
               "--output", str(output), "--library", str(REPO / "runtime/library"),
               "--validator", str(VALIDATOR)]
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                            timeout=300)
    folder = ROOT / "diagnostic" / kind
    (folder / "cpu-compatibility.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(kind + " compatibility failed; see cpu-compatibility.log")
    receipt = json.loads((output / "compatibility.json").read_text())
    if receipt.get("passed") is not True or receipt.get("scope") != "diagnostic software compatibility only":
        raise ValueError("diagnostic compatibility receipt differs")
    for name in ("compatibility.json", "compatibility-analysis.log", "negative-analysis.log"):
        shutil.copyfile(output / name, folder / ("cpu-" + name))
    return {"case_id": case, "passed": True,
            "receipt_sha256": sha(folder / "cpu-compatibility.json"),
            "log_sha256": sha(folder / "cpu-compatibility.log")}


if __name__ == "__main__":
    for suffix in REQUESTS:
        print(json.dumps(run(suffix)), flush=True)
