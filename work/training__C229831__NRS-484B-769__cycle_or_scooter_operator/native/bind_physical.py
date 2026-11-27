"""Run and bind three synthetic engineering motion outcomes per selected case."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent
SCRATCH = REPO / ".runtime-work/c229831-temp"
MANIFEST = FOLDER / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    count = 0
    for entry in manifest["cases"]:
        label = entry["case_id"].rsplit("_", 1)[-1]
        target = FOLDER / "proofs" / label / "physical"
        target.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result_path = target / (kind + ".json")
            log_path = target / (kind + ".log")
            command = [sys.executable, str(FOLDER / "native/prove_physical.py"),
                       "--case", entry["case_id"], "--kind", kind,
                       "--output", str(result_path)]
            env = dict(os.environ)
            env.update({"SCENARIO_PIPELINE_OUTPUT_ROOT": str(SCRATCH),
                        "TMPDIR": str(SCRATCH), "PYTHONDONTWRITEBYTECODE": "1"})
            run = subprocess.run(command, env=env, capture_output=True, text=True)
            log_path.write_text((run.stdout + run.stderr).strip() + "\n")
            if run.returncode:
                raise ValueError("Physical diagnostic failed: " + log_path.read_text()[-500:])
            result = json.loads(result_path.read_text())
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            if result["physical_checks"]["maneuver"]["status"] != expected:
                raise ValueError("Physical diagnostic status mismatch")
            fixtures.append({"kind": kind, "command": " ".join(command),
                             "log": log_path.relative_to(FOLDER).as_posix(),
                             "log_sha256": sha(log_path), "exit_code": run.returncode,
                             "result": result_path.relative_to(FOLDER).as_posix(),
                             "result_sha256": sha(result_path)})
            count += 1
        life = target / "lifecycle.log"
        life.write_text("Synthetic CPU lifecycle ordering: capture_finished, encoders_closed, restoration_verified, native_exit, owner_released, saved_processing_started. Original Native owner release is not claimed.\n")
        receipt = {"format": "c229831-physical-preparation-cpu-v1",
                   "case_id": entry["case_id"],
                   "construction_sha256": entry["construction_sha256"],
                   "fixtures": fixtures,
                   "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                             "restoration_verified", "native_exit",
                                             "owner_released", "saved_processing_started"],
                                 "exit_code": 0,
                                 "log": life.relative_to(FOLDER).as_posix(),
                                 "log_sha256": sha(life)},
                   "original_native_observed": False, "legal_verdict": None}
        receipt_path = target / "receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        entry["physical_preparation"] = {
            "receipt": receipt_path.relative_to(FOLDER).as_posix(),
            "sha256": sha(receipt_path)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"diagnostic_outcomes": count,
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
