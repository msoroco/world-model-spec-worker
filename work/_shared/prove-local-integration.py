"""Run and bind synthetic local delivery integration to the pinned queue proof."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SHARED = Path(__file__).resolve().parent
HARNESS = SHARED / "prove-local-delivery-diagnostic.py"
LOG = SHARED / "local-delivery-diagnostic.log"
PROOF = SHARED / "local-integration-proof.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    command = [sys.executable, str(HARNESS)]
    run = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, timeout=300)
    LOG.write_text(run.stdout)
    if run.returncode:
        raise RuntimeError("Local integration harness failed:\n" + run.stdout[-2500:])
    report = json.loads(run.stdout)
    assert report["format"] == "worker-local-delivery-diagnostic-v1"
    assert report["passed"] is True and report["synthetic_only"] is True
    rows = {entry["scenario"]: entry for entry in report["scenarios"]}
    for name in ("portable_exact_fallback_materialization",
                 "portable_tampered_candidate_rejection",
                 "selected_saved_processing_negative"):
        assert rows[name]["exit_code"] == 0 and rows[name]["executed"] is True
    campaign = rows["primary_fallback_preparation_exact_dispatch_rejected_audit_and_testing_and_training_acceptance"]
    assert campaign["executed"] is True and campaign["tests_run"] == 4
    saved = rows["saved_processing"]
    assert saved["rerun_on_current_host"] is True
    assert saved["positive"] == saved["negative"] == 2
    assert saved["native_executed"] is False
    saved_script = ROOT / "work/training__C382355__NRS-484B-400-1__motor_vehicle_driver/saved-fixture-proof.py"
    assert saved["script_sha256"] == sha(saved_script)
    proof = {
        "format": "worker-local-integration-proof-v1",
        "passed": True,
        "exit_code": run.returncode,
        "command": "python3.11 work/_shared/prove-local-integration.py",
        "log": str(LOG.relative_to(ROOT)),
        "log_sha256": sha(LOG),
        "harness_sha256": sha(HARNESS),
        "scenarios": ["primary_job", "fallback_job", "saved_processing",
                      "rejected_audit", "accepted_targets"],
        "synthetic_only": True,
        "original_native_executed": False,
        "physical_validation_mocked": True,
        "accepted_recordings_claimed": False,
        "observed_test_methods": 4,
        "saved_positive": 2,
        "saved_missing_source_negative": 2,
    }
    PROOF.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
