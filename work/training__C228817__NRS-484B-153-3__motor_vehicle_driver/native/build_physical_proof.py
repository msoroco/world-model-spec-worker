"""Build source-hashed synthetic physical and lifecycle receipts per case."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parents[1]
script = folder / "native/prove_physical.py"
manifest_path = folder / "execution-manifest.json"
manifest = json.loads(manifest_path.read_text())
for number, entry in enumerate(manifest["cases"], 1):
    attempt = root / ".runtime-work/c228817-resume/recorded-only" / f"probe-{number}/positive"
    proof_dir = folder / "native/proofs" / f"probe-{number}/physical"
    proof_dir.mkdir(exist_ok=True)
    receipts = []
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        result = proof_dir / (kind + ".json")
        log = proof_dir / (kind + ".log")
        command = [sys.executable, "-B", str(script), "--attempt", str(attempt),
                   "--kind", kind, "--output", str(result)]
        run = subprocess.run(command, capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError(run.stderr)
        log.write_text(run.stdout.rstrip() + "\n")
        receipts.append({"kind": kind, "command": " ".join(command),
                         "exit_code": run.returncode,
                         "log": str(log.relative_to(folder)), "log_sha256": sha(log),
                         "result": str(result.relative_to(folder)),
                         "result_sha256": sha(result)})
    life_log = proof_dir / "lifecycle.log"
    life_command = [sys.executable, "-B", str(script), "--lifecycle"]
    run = subprocess.run(life_command, capture_output=True, text=True)
    if run.returncode:
        raise RuntimeError(run.stderr)
    life_log.write_text(run.stdout.rstrip() + "\n")
    proof = {"format": "c228817-synthetic-physical-proof-v1",
             "case_id": entry["case_id"],
             "construction_sha256": entry["construction_sha256"],
             "original_native_observed": False,
             "diagnostic_only": True,
             "fixtures": receipts,
             "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                      "restoration_verified", "native_exit",
                                      "owner_released", "saved_processing_started"],
                           "exit_code": 0,
                           "negative_premature_saved_processing_rejected": True,
                           "log": str(life_log.relative_to(folder)),
                           "log_sha256": sha(life_log)}}
    proof_path = proof_dir / "proof.json"
    write(proof_path, proof)
    entry["physical_preparation"] = {"receipt": str(proof_path.relative_to(folder)),
                                     "sha256": sha(proof_path)}
write(manifest_path, manifest)
print("four source-hashed synthetic physical/lifecycle receipts generated")
