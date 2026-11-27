"""Run and bind exact primary/fallback CPU-only construction proofs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in scratch.parts:
        raise ValueError("offline scratch must be under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    python = Path(sys.executable)
    for entry in manifest["cases"]:
        variant = entry["case_id"].removeprefix(manifest["assignment_id"] + "__")
        for candidate, target in ((None, entry), ("fallback1", entry["candidates"][0])):
            label = variant + ("-fallback1" if candidate else "")
            destination = scratch / ("offline-" + label)
            if destination.exists():
                raise ValueError("refusing to replace offline proof " + label)
            command = [str(python), str(REPO / "runtime.py"), "offline",
                       "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--output", str(destination), "--python", str(python)]
            if candidate:
                command += ["--candidate", candidate]
            process = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                                     timeout=300, env=os.environ.copy())
            if process.returncode:
                raise ValueError("offline proof failed " + label + ": " + process.stderr[-1000:])
            raw = (destination / "offline.log").read_text()
            if (f'"case_id": "{entry["case_id"]}"' not in raw or
                    '"offline_check": "passed"' not in raw or
                    not raw.rstrip().endswith("OK")):
                raise ValueError("offline log failed " + label)
            log = ROOT / ("cpu-offline-" + label + ".log")
            log.write_text("\n".join(line.rstrip() for line in raw.splitlines()).rstrip() + "\n")
            target["offline"] = {"command": " ".join(command),
                                 "construction_sha256": target["construction_sha256"],
                                 "exit_code": 0, "log": log.name,
                                 "log_sha256": _sha(log)}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return len(manifest["cases"]) * 2


if __name__ == "__main__":
    print(run())
