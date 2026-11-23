"""Exercise the six Native draft wrappers without importing CARLA or launching it."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from parking_pose import REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "native-draft-manifest.json"
PYTHON = REPO / ".venv-cpu/bin/python"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(kind, candidate):
    case = ROOT.name + "__" + kind
    output = REPO / ".runtime-work" / ("c150041-native-draft-v4-" + candidate + "-" + kind)
    command = [str(PYTHON), str(REPO / "runtime.py"), "offline", "--manifest",
               str(MANIFEST), "--case", case, "--candidate", candidate,
               "--output", str(output), "--python", str(PYTHON)]
    completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                               timeout=300)
    log = ROOT / "diagnostic" / kind / ("cpu-native-draft-" + candidate + ".log")
    log.write_text(completed.stdout + completed.stderr)
    if completed.returncode:
        raise RuntimeError(kind + " " + candidate + " Native draft CPU check failed")
    shutil.copyfile(output / "offline.log", ROOT / "diagnostic" / kind /
                    ("cpu-native-draft-" + candidate + "-tests.log"))
    return {"case_id": case, "candidate_id": candidate, "passed": True,
            "command": " ".join(command), "log": log.relative_to(ROOT).as_posix(),
            "log_sha256": sha(log)}


if __name__ == "__main__":
    for suffix in REQUESTS:
        for selected in ("primary", "fallback1"):
            print(json.dumps(run(suffix, selected)), flush=True)
