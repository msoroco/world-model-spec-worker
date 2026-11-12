"""Bind executed CPU mock physical branches to all selected delivery cases."""
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
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    if len(manifest["cases"]) != 20:
        raise ValueError("Twenty selected cases required")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        folder = HERE / "update060-selected-physical-preparation" / suffix
        fixtures = []
        lifecycle = None
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"):
            output = folder / (kind + ".json")
            log = folder / (kind + ".log")
            cmd = [sys.executable, str(HERE / "run-selected-physical-fixture.py"),
                   "--case", entry["case_id"], "--kind", kind, "--output", str(output)]
            run = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, check=False)
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(run.stdout)
            if run.returncode or not output.is_file():
                raise ValueError("Physical CPU fixture failed: " + suffix + " " + kind + ": " + run.stdout)
            result = json.loads(output.read_text())
            if result.get("cpu_fixture_mock") is not True or result["construction_sha256"] != entry["construction_sha256"]:
                raise ValueError("Fixture provenance or binding absent")
            if kind == "lifecycle":
                lifecycle = {"events": result["events"], "exit_code": 0,
                             "log": str(log.relative_to(HERE)), "log_sha256": sha(log)}
            else:
                if result.get("original_native_motion_verified") is not False:
                    raise ValueError("Mock promoted to original")
                fixtures.append({"kind": kind, "command": " ".join(cmd), "exit_code": 0,
                                 "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                                 "result": str(output.relative_to(HERE)), "result_sha256": sha(output)})
        proof = {"format": "c110919-selected-physical-cpu-fixtures-v1",
                 "case_id": entry["case_id"], "construction_sha256": entry["construction_sha256"],
                 "fixtures_are_cpu_mocks": True, "original_native_motion_verified": False,
                 "original_recordings_accepted": 0, "fixtures": fixtures, "lifecycle": lifecycle}
        proof_path = folder / "proof.json"
        save(proof_path, proof)
        spec = {"receipt": str(proof_path.relative_to(HERE)), "sha256": sha(proof_path)}
        validate(ROOT, HERE, {**entry, "physical_preparation": spec})
        entry["physical_preparation"] = spec
    save(path, manifest)
    print(json.dumps({"selected_cases": 20, "cpu_outcomes": 60, "lifecycle_fixtures": 20,
                      "manifest_sha256": sha(path), "original_native_motion_verified": False,
                      "delivery_ready": False}))


if __name__ == "__main__":
    main()
