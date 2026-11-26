"""Run and bind reproducible CPU motion and lifecycle fixtures for every case."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "selected-native-draft-manifest.json"
SCRIPT = HERE / "prove-physical.py"
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        folder = HERE / "proofs" / "physical" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in KINDS:
            command = [sys.executable, "-B", str(SCRIPT), "--case", case, "--kind", kind]
            run = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=30)
            if run.returncode or run.stderr:
                raise ValueError("Physical fixture failed: " + suffix + " " + kind + " " + run.stderr)
            result = json.loads(run.stdout)
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            if result["physical_checks"]["maneuver"]["status"] != expected:
                raise ValueError("Fixture source did not realize expected physical diagnostic")
            result_path = folder / (kind + ".json")
            log_path = folder / (kind + ".log")
            write(result_path, result)
            log_path.write_text("CPU source-derived fixture " + kind + " passed for " + case + "\n")
            fixtures.append({"kind": kind, "command": " ".join(command),
                             "exit_code": 0, "result": str(result_path.relative_to(HERE)),
                             "result_sha256": sha(result_path), "log": str(log_path.relative_to(HERE)),
                             "log_sha256": sha(log_path)})
        command = [sys.executable, "-B", str(SCRIPT), "--case", case, "--kind", "lifecycle"]
        run = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=30)
        if run.returncode or run.stderr:
            raise ValueError("Lifecycle fixture failed: " + suffix + " " + run.stderr)
        life = json.loads(run.stdout)
        life_log = folder / "lifecycle.log"
        life_log.write_text("CPU capture closure and saved-processing order passed for " + case + "\n")
        life.update({"log": str(life_log.relative_to(HERE)), "log_sha256": sha(life_log)})
        receipt = {"format": "c247014-physical-preparation-v1", "case_id": case,
                   "construction_sha256": entry["construction_sha256"],
                   "fixtures": fixtures, "lifecycle": life,
                   "original_native_observed": False, "legal_judgment": None}
        receipt_path = folder / "receipt.json"
        write(receipt_path, receipt)
        entry["physical_preparation"] = {"receipt": str(receipt_path.relative_to(HERE)),
                                         "sha256": sha(receipt_path)}
    write(MANIFEST, manifest)
    print(json.dumps({"bound": len(manifest["cases"]), "manifest_sha256": sha(MANIFEST)}, sort_keys=True))


if __name__ == "__main__":
    main()
