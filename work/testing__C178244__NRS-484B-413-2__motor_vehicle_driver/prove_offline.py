"""Run pinned exact-case offline checks for all primary and fallback bundles."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def main() -> None:
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "c178244-offline-reviewed2"
    scratch.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        tag = entry["case_id"].rsplit("__", 1)[-1]
        for candidate in (None, *entry["candidates"]):
            candidate_id = "primary" if candidate is None else candidate["id"]
            target = entry if candidate is None else candidate
            output = scratch / f"{tag}-{candidate_id}"
            if output.exists():
                raise ValueError("offline output already exists: " + str(output))
            command = [sys.executable, str(REPO / "runtime.py"), "offline",
                       "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--output", str(output)]
            if candidate is not None:
                command += ["--candidate", candidate_id]
            run = subprocess.run(command, cwd=REPO, text=True,
                                 capture_output=True, check=False)
            log_name = f"proof-offline-{tag}-{candidate_id}.log"
            log = ROOT / log_name
            source = output / "offline.log"
            evidence = source.read_text() if source.is_file() else run.stdout + run.stderr
            log.write_text(evidence.rstrip() + "\n")
            if run.returncode:
                raise RuntimeError(f"offline {tag}/{candidate_id} failed: {run.stderr}")
            target["offline"] = {"command": " ".join(command),
                                 "construction_sha256": target["construction_sha256"],
                                 "exit_code": 0, "log": log_name,
                                 "log_sha256": sha256(log.read_bytes()).hexdigest()}
            MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
