"""Reprove all six selected physical outcome and lifecycle CPU fixtures."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.physical_preparation import validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if len(manifest["cases"]) != 6:
        raise ValueError("Six selected Walk cases required")
    for case in manifest["cases"]:
        suffix = case["case_id"].removeprefix(HERE.name + "__")
        script = ("run-sweep-physical-mock-update201.py" if suffix.startswith("right_of_way_physical_context-")
                  else "run-selected-physical-mock-update201.py")
        folder = HERE / "update201-selected-physical" / suffix
        if folder.exists():
            raise ValueError("Retain prior physical proof: " + str(folder))
        fixtures = []
        lifecycle = None
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"):
            result_path = folder / (kind + ".json")
            log = folder / (kind + ".log")
            command = [sys.executable, str(HERE / script), "--case", suffix,
                       "--kind", kind, "--output", str(result_path)]
            run = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=180)
            folder.mkdir(parents=True, exist_ok=True)
            log.write_text(run.stdout)
            if run.returncode or not result_path.is_file():
                raise ValueError("Physical CPU mock failed " + suffix + " " + kind + ": " + run.stdout)
            result = json.loads(result_path.read_text())
            if (result.get("cpu_fixture_mock") is not True or
                    result.get("original_native_motion_verified") is not False or
                    result.get("original_walk_pixels_verified") is not False or
                    result["construction_sha256"] != case["construction_sha256"]):
                raise ValueError("Physical CPU proof identity or provenance differs")
            if kind == "lifecycle":
                lifecycle = {"events": result["events"], "exit_code": 0,
                             "log": log.relative_to(HERE).as_posix(), "log_sha256": sha(log)}
            else:
                fixtures.append({"kind": kind, "command": " ".join(command),
                                 "exit_code": 0, "log": log.relative_to(HERE).as_posix(),
                                 "log_sha256": sha(log),
                                 "result": result_path.relative_to(HERE).as_posix(),
                                 "result_sha256": sha(result_path)})
        proof = {"format": "c111256-update201-selected-physical-v1",
                 "case_id": case["case_id"],
                 "construction_sha256": case["construction_sha256"],
                 "fixtures_are_cpu_mocks": True,
                 "original_native_motion_verified": False,
                 "original_walk_pixels_verified": False,
                 "fixtures": fixtures, "lifecycle": lifecycle}
        receipt = folder / "proof.json"
        save(receipt, proof)
        spec = {"receipt": receipt.relative_to(HERE).as_posix(), "sha256": sha(receipt)}
        validate(ROOT, HERE, {**case, "physical_preparation": spec})
        case["physical_preparation"] = spec
        save(manifest_path, manifest)
        print(suffix, "physical fixtures and lifecycle passed", flush=True)
    print(json.dumps({"selected_cases": 6, "cpu_outcomes": 18, "lifecycle_fixtures": 6,
                      "manifest_sha256": sha(manifest_path),
                      "original_native_motion_verified": False}))


if __name__ == "__main__":
    main()
