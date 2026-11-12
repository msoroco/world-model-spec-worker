"""Bind replayed two-case C10014 CPU motion and lifecycle mock receipts."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline"))
from scenario_pipeline.worker_exchange.physical_preparation import validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if len(manifest["cases"]) != 2:
        raise ValueError("Two selected crosswalk cases required")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        folder = HERE / "update024-selected-physical" / suffix
        fixtures = []
        lifecycle = None
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"):
            output = folder / (kind + ".json")
            log = folder / (kind + ".log")
            command = [sys.executable, str(HERE / "run-selected-physical-mock.py"),
                       "--case", suffix, "--kind", kind, "--output", str(output)]
            run = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, check=False)
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(run.stdout)
            if run.returncode or not output.is_file():
                raise ValueError("Crosswalk physical fixture failed: " + suffix + " " + kind + ": " + run.stdout)
            result = json.loads(output.read_text())
            if result.get("cpu_fixture_mock") is not True or result["construction_sha256"] != entry["construction_sha256"]:
                raise ValueError("Crosswalk fixture mock or construction binding missing")
            if kind == "lifecycle":
                lifecycle = {"events": result["events"], "exit_code": 0,
                             "log": str(log.relative_to(HERE)), "log_sha256": sha(log)}
            else:
                if result.get("original_native_motion_verified") is not False:
                    raise ValueError("Crosswalk mock promoted to original Native")
                fixtures.append({"kind": kind, "command": " ".join(command), "exit_code": 0,
                                 "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                                 "result": str(output.relative_to(HERE)), "result_sha256": sha(output)})
        proof = {"format": "c10316-selected-physical-cpu-fixtures-v1",
                 "case_id": entry["case_id"], "construction_sha256": entry["construction_sha256"],
                 "fixtures_are_cpu_mocks": True, "original_native_motion_verified": False,
                 "practicability_verified": False,
                 "fixtures": fixtures, "lifecycle": lifecycle}
        proof_path = folder / "proof.json"
        save(proof_path, proof)
        spec = {"receipt": str(proof_path.relative_to(HERE)), "sha256": sha(proof_path)}
        validate(ROOT, HERE, {**entry, "physical_preparation": spec})
        entry["physical_preparation"] = spec
    save(manifest_path, manifest)
    print(json.dumps({"selected_cases": 2, "cpu_outcomes": 6, "lifecycle_fixtures": 2,
                      "manifest_sha256": sha(manifest_path), "original_native_motion_verified": False}))


if __name__ == "__main__":
    main()
