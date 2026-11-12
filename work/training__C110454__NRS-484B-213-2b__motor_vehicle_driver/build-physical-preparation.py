"""Create and bind six explicit CPU branch fixtures, without physical claims."""
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


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    index = json.loads((HERE / "update025-selected-six-index.json").read_text())
    cases = manifest["cases"]
    if len(cases) != 6 or len(index["results"]) != 24:
        raise ValueError("Current six-case diagnostic matrix required")
    for entry in cases:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        chain = next(row for row in index["results"] if row["case_id"] == entry["case_id"]
                     and row["candidate_id"] == "primary")
        if sha(HERE / chain["proof"]) != chain["sha256"]:
            raise ValueError("Current selected chain proof changed")
        folder = HERE / "update028-physical-preparation" / suffix
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"):
            result = folder / (kind + ".json")
            log = folder / (kind + ".log")
            command = [".venv-cpu/bin/python", str(HERE.relative_to(ROOT) / "run-physical-fixture.py"),
                       "--case", entry["case_id"], "--kind", kind,
                       "--output", str(result.relative_to(ROOT))]
            run = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, check=False)
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(run.stdout)
            if run.returncode or not result.is_file():
                raise ValueError("Physical CPU fixture failed: " + kind + " " + suffix)
            if kind == "lifecycle":
                lifecycle = {"events": json.loads(result.read_text())["events"],
                             "exit_code": 0, "log": str(log.relative_to(HERE)),
                             "log_sha256": sha(log)}
            else:
                fixture_result = json.loads(result.read_text())
                if (fixture_result.get("cpu_fixture_mock") is not True or
                    fixture_result.get("original_native_motion_verified") is not False):
                    raise ValueError("Physical fixture lacks mock provenance")
                fixtures.append({"kind": kind, "command": " ".join(command),
                                 "exit_code": 0, "log": str(log.relative_to(HERE)),
                                 "log_sha256": sha(log),
                                 "result": str(result.relative_to(HERE)),
                                 "result_sha256": sha(result)})
        proof = {"format": "c110454-physical-preparation-cpu-fixtures-v1",
                 "case_id": entry["case_id"],
                 "construction_sha256": entry["construction_sha256"],
                 "fixtures_are_cpu_mocks": True,
                 "original_native_motion_verified": False,
                 "original_recordings_accepted": 0,
                 "fixtures": fixtures, "lifecycle": lifecycle}
        proof_path = folder / "proof.json"
        save(proof_path, proof)
        spec = {"receipt": str(proof_path.relative_to(HERE)), "sha256": sha(proof_path)}
        validate(ROOT, HERE, {**entry, "physical_preparation": spec})
        entry["physical_preparation"] = spec
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"selected_cases": len(cases), "cpu_motion_fixtures": 3 * len(cases),
                      "lifecycle_fixtures": len(cases),
                      "manifest_sha256": sha(manifest_path),
                      "original_native_motion_verified": 0}))


if __name__ == "__main__":
    main()
