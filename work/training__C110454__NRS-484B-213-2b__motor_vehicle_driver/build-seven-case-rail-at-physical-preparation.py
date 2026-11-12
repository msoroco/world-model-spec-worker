"""Bind rail-at CPU motion and lifecycle fixtures to its exact construction."""
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


manifest = HERE / "update035-seven-case-probe-manifest.json"
entry = next(x for x in json.loads(manifest.read_text())["cases"]
             if x["case_id"].endswith("__rail_at"))
folder = HERE / "update035-rail-at-physical-preparation"
folder.mkdir(exist_ok=True)
fixtures = []
for kind in ("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"):
    result, log = folder / (kind + ".json"), folder / (kind + ".log")
    cmd = [sys.executable, str(HERE / "run-physical-fixture.py"),
           "--manifest", str(manifest), "--run-root",
           str(ROOT / ".runtime-work/c110454-update035-seven-probe"),
           "--case", entry["case_id"], "--kind", kind, "--output", str(result)]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    log.write_text(run.stdout + run.stderr)
    if run.returncode or not result.is_file():
        raise ValueError("Rail-at physical CPU fixture failed: " + kind + " " + log.read_text())
    if kind == "lifecycle":
        lifecycle = {"events": json.loads(result.read_text())["events"],
                     "exit_code": 0, "log": str(log.relative_to(HERE)),
                     "log_sha256": sha(log)}
    else:
        value = json.loads(result.read_text())
        assert value["cpu_fixture_mock"] is True and value["original_native_motion_verified"] is False
        fixtures.append({"kind": kind, "command": " ".join(cmd), "exit_code": 0,
                         "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                         "result": str(result.relative_to(HERE)), "result_sha256": sha(result)})
proof = {"format": "c110454-physical-preparation-cpu-fixtures-v1",
         "case_id": entry["case_id"], "construction_sha256": entry["construction_sha256"],
         "fixtures_are_cpu_mocks": True, "original_native_motion_verified": False,
         "original_recordings_accepted": 0, "fixtures": fixtures, "lifecycle": lifecycle}
path = folder / "proof.json"
path.write_text(json.dumps(proof, indent=2) + "\n")
validate(ROOT, HERE, {**entry, "physical_preparation": {
    "receipt": str(path.relative_to(HERE)), "sha256": sha(path)}})
print(json.dumps({"case_id": entry["case_id"], "proof_sha256": sha(path),
                  "cpu_motion_fixtures": 3, "lifecycle_fixtures": 1,
                  "original_native_motion_verified": False}))
