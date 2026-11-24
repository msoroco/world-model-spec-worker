"""Generate durable exact-case CPU fixture and ownership-order proofs."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SCRIPT = ROOT / "selected-v2/physical_fixture.py"
ORDER = ["capture_finished", "encoders_closed", "restoration_verified",
         "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for index in (1, 2):
    case = f"{ROOT.name}__witness_{index}"
    folder = ROOT / "selected-v2/physical" / f"witness{index}"
    folder.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        result = folder / f"{kind}.json"
        log = folder / f"{kind}.log"
        command = [sys.executable, str(SCRIPT), "--case", case,
                   "--kind", kind, "--result", str(result)]
        run = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=False)
        log.write_text(run.stdout + run.stderr)
        assert run.returncode == 0, log.read_text()
        payload = json.loads(result.read_text())
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        assert payload["physical_checks"]["maneuver"]["status"] == expected
        fixtures.append({"kind": kind,
                         "command": " ".join(command),
                         "exit_code": run.returncode,
                         "log": str(log.relative_to(ROOT)), "log_sha256": sha(log),
                         "result": str(result.relative_to(ROOT)), "result_sha256": sha(result)})
    life_log = folder / "lifecycle.log"
    life_log.write_text(json.dumps({"format": "c131364-ownership-order-cpu-fixture",
                                    "case_id": case, "events": ORDER,
                                    "fake_native_source_test_sha256": sha(ROOT / "v2-native-draft/fake-native-test.log"),
                                    "simulation_started": False,
                                    "physical_acceptance_claimed": False}) + "\n")
    proof = {"format": "c131364-physical-preparation-cpu-v2",
             "case_id": case,
             "construction_sha256": json.loads((ROOT / "selected-v2-manifest.json").read_text())["cases"][index - 1]["construction_sha256"],
             "fixtures": fixtures,
             "lifecycle": {"events": ORDER, "exit_code": 0,
                           "log": str(life_log.relative_to(ROOT)),
                           "log_sha256": sha(life_log)},
             "fixture_only": True, "physical_acceptance_claimed": False}
    proof_path = folder / "proof.json"
    proof_path.write_text(json.dumps(proof, indent=2) + "\n")
    print(case, sha(proof_path))
