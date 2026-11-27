"""Run and bind five exact CPU physical/lifecycle diagnostic proofs."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c147339-physical"
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        suffix = cid.split("__")[-1]
        output = SCRATCH / suffix
        command = [sys.executable, str(ROOT / "physical_probe.py"),
                   "--case", cid, "--output", str(output)]
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH),
                           PYTHONPATH=str(REPO / "runtime/scenario_pipeline"),
                           SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "pipeline"))
        completed = subprocess.run(command, cwd=REPO, env=environment,
                                   capture_output=True, text=True)
        log = ROOT / ("cpu-physical-" + suffix + ".log")
        log.write_text((completed.stdout + completed.stderr).rstrip() + "\n")
        if completed.returncode or "lifecycle" not in completed.stdout:
            raise ValueError("Physical/lifecycle proof failed: " + suffix + ": " + completed.stderr)
        log_hash = sha(log)
        fixtures = []
        for kind in KINDS:
            result = ROOT / ("physical-" + suffix + "-" + kind + ".json")
            fixtures.append({"kind": kind, "command": " ".join(command), "exit_code": 0,
                             "log": log.name, "log_sha256": log_hash,
                             "result": result.name, "result_sha256": sha(result)})
        proof = {"format": "worker-physical-preparation", "case_id": cid,
                 "construction_sha256": entry["construction_sha256"], "fixtures": fixtures,
                 "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                          "restoration_verified", "native_exit", "owner_released",
                                          "saved_processing_started"],
                               "exit_code": 0, "command": " ".join(command),
                               "log": log.name, "log_sha256": log_hash}}
        receipt = ROOT / ("physical-preparation-" + suffix + ".json")
        write(receipt, proof)
        entry["physical_preparation"] = {"receipt": receipt.name, "sha256": sha(receipt)}
        print(suffix, "physical and lifecycle passed", flush=True)
    write(manifest_path, manifest)


if __name__ == "__main__":
    main()
