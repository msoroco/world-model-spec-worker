"""Run and bind all exact driveway construction checks through runtime.py."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c213645-owner"
SCRATCH.mkdir(parents=True, exist_ok=True)
MANIFEST = HERE / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for entry in manifest["cases"]:
    name = entry["case_id"].split("__")[-1]
    output = SCRATCH / ("offline-" + name + "-primary-v3")
    command = [sys.executable, str(REPO / "runtime.py"), "offline",
               "--manifest", str(MANIFEST), "--case", entry["case_id"],
               "--output", str(output), "--python", sys.executable]
    env = dict(os.environ)
    env["TMPDIR"] = str(SCRATCH)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH / "pipeline")
    subprocess.run(command, cwd=REPO, env=env, check=True)
    log = HERE / ("cpu-offline-" + name + "-primary.log")
    log.write_text((output / "offline.log").read_text().rstrip() + "\n")
    entry["offline"] = {"command": " ".join(command), "exit_code": 0,
                        "log": log.name, "log_sha256": sha(log),
                        "construction_sha256": entry["construction_sha256"]}
MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
