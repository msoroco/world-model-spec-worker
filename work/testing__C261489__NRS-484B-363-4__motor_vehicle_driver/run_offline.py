"""Run and bind exact primary construction checks; scratch stays in .runtime-work."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
MANIFEST = HERE / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work" / "c261489-owner-nov27b"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_log(source: Path, destination: Path) -> None:
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    destination.write_text("\n".join(lines) + "\n")


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH))
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        name = case_id[len(ASSIGNMENT) + 2:]
        destination = SCRATCH / ("offline-" + name + "-v7")
        command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                   "offline", "--manifest", str(MANIFEST), "--case", case_id,
                   "--output", str(destination), "--python", str(REPO / ".venv-cpu/bin/python")]
        if not destination.exists():
            process = subprocess.run(command, cwd=REPO, env=env, text=True,
                                     capture_output=True, timeout=300)
            if process.returncode:
                print(process.stdout, process.stderr, file=sys.stderr)
                raise RuntimeError(f"offline failed for {name}: {process.returncode}")
        log = destination / "offline.log"
        if not log.is_file() or "OK" not in log.read_text():
            raise ValueError("missing passing exact offline log: " + name)
        copy = HERE / ("cpu-offline-" + name + ".log")
        clean_log(log, copy)
        entry["offline"] = {
            "command": " ".join(command), "exit_code": 0,
            "construction_sha256": entry["construction_sha256"],
            "log": copy.name, "log_sha256": sha(copy),
        }
        print(name, "offline passed")
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
