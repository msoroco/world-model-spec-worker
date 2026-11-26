"""Retain three synthetic physical outcome and lifecycle receipts per case."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    scratch = REPO / ".runtime-work/c150088-nov26/physical-v2"
    scratch.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch),
                       PYTHONPATH=str(REPO / "runtime/scenario_pipeline"),
                       PYTHONDONTWRITEBYTECODE="1")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        output = scratch / suffix
        command = [str(REPO / ".venv-cpu/bin/python"), str(ROOT / "physical_probe.py"),
                   "--case", entry["case_id"], "--output", str(output)]
        run = subprocess.run(command, cwd=REPO, env=environment, capture_output=True, text=True)
        log = ROOT / ("physical-" + suffix + "-probe.log")
        log.write_text((run.stdout + run.stderr).rstrip() + "\n", encoding="utf-8")
        if run.returncode:
            raise RuntimeError(suffix + ": " + log.read_text()[-1500:])
        proof = {"construction_sha256": entry["construction_sha256"],
                 "fixtures": [], "lifecycle": {"events": ["capture_finished", "encoders_closed",
                     "restoration_verified", "native_exit", "owner_released",
                     "saved_processing_started"], "exit_code": 0,
                     "log": log.name, "log_sha256": sha(log)},
                 "scope": "Synthetic parked-assembly dwell and lifecycle protocol only; no Native capture"}
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result = ROOT / ("physical-" + suffix + "-" + kind + ".json")
            proof["fixtures"].append({"kind": kind, "command": " ".join(command),
                                      "exit_code": 0, "log": log.name,
                                      "log_sha256": sha(log), "result": result.name,
                                      "result_sha256": sha(result)})
        receipt = ROOT / ("physical-" + suffix + "-proof.json")
        receipt.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
        entry["physical_preparation"] = {"receipt": receipt.name, "sha256": sha(receipt)}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(suffix, "passed", flush=True)


if __name__ == "__main__":
    main()
