"""Build replayable physical CPU receipts for the two-case probe."""
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


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def main():
    source = HERE / "update017-selected-pair-probe-manifest.json"
    manifest = json.loads(source.read_text())
    index = json.loads((HERE / "update017-selected-pair-probe-index.json").read_text())
    if index["manifest_sha256"] != sha(source) or len(index["results"]) != 8:
        raise ValueError("Selected-pair candidate proof index changed")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        proof_row = next(row for row in index["results"] if row["case_id"] == entry["case_id"]
                         and row["candidate_id"] == "primary")
        if sha(HERE / proof_row["proof"]) != proof_row["sha256"]:
            raise ValueError("Primary selected-pair CPU proof changed")
        folder = HERE / "update019-physical-preparation" / suffix
        fixtures = []
        lifecycle = None
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"):
            result = folder / (kind + ".json")
            log = folder / (kind + ".log")
            cmd = [".venv-cpu/bin/python", str((HERE / "run-physical-fixture.py").relative_to(ROOT)),
                   "--case", suffix, "--kind", kind, "--output", str(result.relative_to(ROOT))]
            run = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, check=False)
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(run.stdout)
            if run.returncode or not result.is_file():
                raise ValueError("Physical fixture failed: " + suffix + " " + kind + ": " + run.stdout)
            if kind == "lifecycle":
                events = json.loads(result.read_text())["events"]
                lifecycle = {"events": events, "exit_code": 0,
                             "log": str(log.relative_to(HERE)), "log_sha256": sha(log)}
            else:
                outcome = json.loads(result.read_text())
                if outcome.get("cpu_fixture_mock") is not True or outcome.get("original_native_motion_verified") is not False:
                    raise ValueError("Physical fixture is missing mock provenance")
                fixtures.append({"kind": kind, "command": " ".join(cmd), "exit_code": 0,
                                 "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                                 "result": str(result.relative_to(HERE)), "result_sha256": sha(result)})
        proof = {"format": "c110919-physical-preparation-cpu-fixtures-v1",
                 "case_id": entry["case_id"], "construction_sha256": entry["construction_sha256"],
                 "fixtures_are_cpu_mocks": True, "original_native_motion_verified": False,
                 "original_recordings_accepted": 0, "fixtures": fixtures, "lifecycle": lifecycle}
        proof_path = folder / "proof.json"
        save(proof_path, proof)
        spec = {"receipt": str(proof_path.relative_to(HERE)), "sha256": sha(proof_path)}
        validate(ROOT, HERE, {**entry, "physical_preparation": spec})
        entry["physical_preparation"] = spec
    manifest["status"] = "partial_selected_pair_physical_probe"
    manifest["source_probe_manifest_sha256"] = sha(source)
    bound = HERE / "update019-physical-binding-manifest.json"
    save(bound, manifest)
    print(json.dumps({"cases": len(manifest["cases"]), "cpu_outcomes": 6,
                      "lifecycle_fixtures": 2, "bound_manifest_sha256": sha(bound),
                      "original_native_motion_verified": False,
                      "prior_candidate_receipts_bound_to_source_probe": True}))


if __name__ == "__main__":
    main()
