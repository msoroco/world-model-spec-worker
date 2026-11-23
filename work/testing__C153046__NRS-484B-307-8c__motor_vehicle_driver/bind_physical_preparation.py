"""Bind exact diagnostic physical outcomes and lifecycle CPU proofs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = ROOT / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work/c153046-physical-fixtures"))
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        folder = ROOT / "diagnostics" / suffix
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result = folder / (kind + "-result.json")
            log = folder / (kind + "-proof.log")
            command = [sys.executable, str(ROOT / "prove_physical_outcome.py"),
                       "--case", case_id, "--kind", kind, "--output", str(result)]
            with log.open("w") as stream:
                process = subprocess.run(command, cwd=REPO, env=environment,
                                         stdout=stream, stderr=subprocess.STDOUT, timeout=60)
            if process.returncode:
                raise ValueError("physical fixture failed: " + str(log))
            fixtures.append({"kind": kind, "command": " ".join(command), "exit_code": 0,
                             "log": str(log.relative_to(ROOT)), "log_sha256": sha(log),
                             "result": str(result.relative_to(ROOT)), "result_sha256": sha(result)})
        lifecycle_log = folder / "lifecycle-proof.log"
        lifecycle_command = [sys.executable, str(ROOT / "prove_physical_lifecycle.py"), "--case", case_id]
        with lifecycle_log.open("w") as stream:
            process = subprocess.run(lifecycle_command, cwd=REPO, env=environment,
                                     stdout=stream, stderr=subprocess.STDOUT, timeout=60)
        if process.returncode:
            raise ValueError("lifecycle fixture failed: " + str(lifecycle_log))
        receipt = {"format": "c153046-synthetic-physical-preparation",
                   "case_id": case_id, "construction_sha256": entry["construction_sha256"],
                   "fixtures": fixtures,
                   "lifecycle": {"events": EVENTS, "exit_code": 0,
                                 "command": " ".join(lifecycle_command),
                                 "log": str(lifecycle_log.relative_to(ROOT)),
                                 "log_sha256": sha(lifecycle_log)},
                   "scope": "synthetic CPU physical protocol; original motion and owner lifecycle unverified"}
        receipt_path = folder / "physical-preparation.json"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        entry["physical_preparation"] = {"receipt": str(receipt_path.relative_to(ROOT)),
                                          "sha256": sha(receipt_path)}
        print("pinned physical outcome and lifecycle CPU fixtures passed", suffix, flush=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
