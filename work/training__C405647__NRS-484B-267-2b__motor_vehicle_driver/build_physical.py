"""Bind five synthetic emergency-maneuver and lifecycle CPU proofs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c405647-check"
SCRIPT = ROOT / "physical_proof.py"
MANIFEST = ROOT / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        attempt = SCRATCH / ("saved-attempt-" + suffix + "-v1")
        proof = ROOT / "native/proofs" / suffix / "physical"
        proof.mkdir(parents=True, exist_ok=True)
        receipts = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result_path = proof / (kind + ".json")
            log_path = proof / (kind + ".log")
            command = [sys.executable, "-B", str(SCRIPT), "--attempt", str(attempt),
                       "--kind", kind, "--output", str(result_path)]
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(kind + ": " + result.stderr)
            log_path.write_text(result.stdout.rstrip() + "\n")
            receipts.append({"kind": kind, "command": "PYTHONPATH=" + str(ROOT) + " " +
                             " ".join(command), "exit_code": 0,
                             "log": str(log_path.relative_to(ROOT)), "log_sha256": sha(log_path),
                             "result": str(result_path.relative_to(ROOT)),
                             "result_sha256": sha(result_path)})
        life_log = proof / "lifecycle.log"
        command = [sys.executable, "-B", str(SCRIPT), "--lifecycle"]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        life_log.write_text(result.stdout.rstrip() + "\n")
        receipt = {"format": "c405647-2b-synthetic-physical-proof-v1",
                   "case_id": entry["case_id"],
                   "construction_sha256": entry["construction_sha256"],
                   "original_native_observed": False, "diagnostic_only": True,
                   "fixtures": receipts,
                   "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                            "restoration_verified", "native_exit",
                                            "owner_released", "saved_processing_started"],
                                 "exit_code": 0,
                                 "negative_premature_saved_processing_rejected": True,
                                 "log": str(life_log.relative_to(ROOT)),
                                 "log_sha256": sha(life_log)}}
        receipt_path = proof / "proof.json"
        write(receipt_path, receipt)
        entry["physical_preparation"] = {"receipt": str(receipt_path.relative_to(ROOT)),
                                         "sha256": sha(receipt_path)}
    write(MANIFEST, manifest)
    print("Five exact synthetic emergency maneuver/lifecycle receipts generated")


if __name__ == "__main__":
    main()
