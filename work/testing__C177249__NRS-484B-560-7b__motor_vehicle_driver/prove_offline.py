"""Run exact primary and fallback offline checks; retain compact clean logs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import railway_7b as law

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
SCRATCH = REPO / ".runtime-work" / "c177249-offline"


def clean_copy(source, target):
    data = source.read_text().rstrip() + "\n"
    temporary = SCRATCH / (target.name + ".tmp")
    temporary.write_text(data)
    os.replace(temporary, target)


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for name in law.CASES:
        case = AID + "__" + name
        for candidate in ("primary", "fallback1"):
            output = SCRATCH / (name + "-" + candidate)
            if output.exists():
                raise ValueError("offline scratch already exists: " + str(output))
            command = [sys.executable, str(REPO / "runtime.py"), "offline",
                       "--manifest", str(HERE / "execution-manifest.json"),
                       "--case", case, "--candidate", candidate, "--output", str(output)]
            process = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                                     env={**os.environ, "TMPDIR": str(REPO / ".runtime-work")})
            if process.returncode:
                print(process.stdout + process.stderr, file=sys.stderr)
                raise ValueError("offline failed: " + name + "/" + candidate)
            receipt = json.loads(process.stdout)
            if not receipt.get("offline_passed") or receipt.get("candidate_id") != candidate:
                raise ValueError("offline receipt mismatch")
            clean_copy(output / "offline.log", HERE / ("cpu-offline-" + name + "-" + candidate + ".log"))
            print(name, candidate, "passed", flush=True)


if __name__ == "__main__":
    main()
