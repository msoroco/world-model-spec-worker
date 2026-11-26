"""Run pinned offline construction checks for all exact route cases/candidates."""
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "c179789-offline-v3"
    scratch.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        tag = entry["case_id"].rsplit("__", 1)[-1]
        for candidate in (None, *entry["candidates"]):
            selected = entry if candidate is None else candidate
            candidate_id = "primary" if candidate is None else candidate["id"]
            output = scratch / (tag + "-" + candidate_id)
            if output.exists():
                raise ValueError("offline output already exists: " + str(output))
            command = [sys.executable, str(REPO / "runtime.py"), "offline",
                       "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--output", str(output)]
            if candidate is not None:
                command.extend(["--candidate", candidate_id])
            run = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
            log = ROOT / ("proof-offline-" + tag + "-" + candidate_id + ".log")
            source = output / "offline.log"
            log.write_text(((source.read_text() if source.is_file() else run.stdout + run.stderr).rstrip()) + "\n")
            if run.returncode:
                raise RuntimeError("offline failed: " + tag + "/" + candidate_id + ": " + run.stderr)
            selected["offline"] = {"command": " ".join(command),
                                   "construction_sha256": selected["construction_sha256"],
                                   "exit_code": 0, "log": log.name,
                                   "log_sha256": sha(log)}
            MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
