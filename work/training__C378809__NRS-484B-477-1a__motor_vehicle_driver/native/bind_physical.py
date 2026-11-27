"""Run and bind three physical CPU outcomes and lifecycle per selected case."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    manifest_path = PACKAGE / "selected-draft-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        output = PACKAGE / "proofs/physical" / suffix
        fixtures = []
        lifecycle = None
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"):
            result_path = output / (kind + ".json")
            log_path = output / (kind + ".log")
            command = [sys.executable, "-B", str(HERE / "physical_lifecycle_cpu.py"),
                       "--case", case_id, "--kind", kind, "--output", str(result_path)]
            process = subprocess.run(command, cwd=REPO, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(process.stdout.rstrip() + "\n")
            if process.returncode or not result_path.is_file():
                raise ValueError("Physical CPU proof failed: " + kind + " " + process.stdout)
            result = json.loads(result_path.read_text())
            if result["construction_sha256"] != entry["construction_sha256"]:
                raise ValueError("Physical CPU result binds other construction")
            if kind == "lifecycle":
                lifecycle = {"events": result["events"], "exit_code": 0,
                             "log": str(log_path.relative_to(PACKAGE)),
                             "log_sha256": sha(log_path)}
            else:
                fixtures.append({"kind": kind, "command": " ".join(command),
                                 "exit_code": 0,
                                 "log": str(log_path.relative_to(PACKAGE)),
                                 "log_sha256": sha(log_path),
                                 "result": str(result_path.relative_to(PACKAGE)),
                                 "result_sha256": sha(result_path)})
        proof = {"format": "c378809-physical-lifecycle-cpu-v1",
                 "case_id": case_id,
                 "construction_sha256": entry["construction_sha256"],
                 "synthetic_diagnostic_only": True,
                 "original_native_motion_verified": False,
                 "physical_acceptance_claimed": False,
                 "fixtures": fixtures, "lifecycle": lifecycle}
        proof_path = output / "proof.json"
        save(proof_path, proof)
        entry["physical_preparation"] = {
            "receipt": str(proof_path.relative_to(PACKAGE)),
            "sha256": sha(proof_path)}
    save(manifest_path, manifest)
    print(json.dumps({"cases": len(manifest["cases"]),
                      "physical_fixtures": len(manifest["cases"]) * 3,
                      "lifecycle_fixtures": len(manifest["cases"])}))


if __name__ == "__main__":
    main()
