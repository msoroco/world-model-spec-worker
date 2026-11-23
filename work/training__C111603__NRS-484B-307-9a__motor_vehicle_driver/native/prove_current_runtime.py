"""Rebuild and verify the unselected C111603 CPU draft on the pinned runtime."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STEPS = (
    "build.py", "saved.py", "build_offline.py", "prove_offline.py",
    "prove_request.py", "prove_saved.py", "prove_fallback_quality.py",
    "prove_capture_preflight.py", "audit_offline.py", "audit_request.py",
    "audit_fallback_quality.py", "audit_original_shape.py",
    "prove_capture_quality.py",
)
RECEIPTS = (
    "manifest.json", "saved-manifest.json", "draft-execution-manifest.json",
    "pinned-offline-proof.json", "request-proof.json", "saved-proof.json",
    "fallback-quality-proof.json", "capture-preflight-proof.json",
    "pinned-offline-audit.json", "independent-audit.json",
    "fallback-quality-audit.json", "original-shape-audit.json",
    "capture-quality-shape-proof.json",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    env = os.environ.copy()
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(ROOT / ".runtime-work" / "c111603")
    results = []
    for name in STEPS:
        command = [sys.executable, str(HERE / name)]
        done = subprocess.run(command, cwd=ROOT, env=env,
                              capture_output=True, text=True)
        output = done.stdout + done.stderr
        log = HERE / (name.removesuffix(".py") + ".current.log")
        log.write_text(output)
        results.append({"command": f".venv-cpu/bin/python work/{HERE.parent.name}/native/{name}",
                        "exit_code": done.returncode,
                        "log": log.name, "log_sha256": sha(log)})
        if done.returncode:
            raise RuntimeError(f"{name} failed; inspect {log}")
    result = {
        "format": "c111603-current-runtime-cpu-draft-proof-v1",
        "assignment_id": HERE.parent.name,
        "source_sha256": sha(ROOT / "inputs" / HERE.parent.name / "assignment.json"),
        "steps": results,
        "receipt_sha256": {name: sha(HERE / name) for name in RECEIPTS},
        "case_count": 2, "candidate_count": 8, "frames_per_candidate": 600,
        "camera_names": ["overview", "approach", "reference_corner", "driver_reference"],
        "original_native_observed": False, "delivery_ready": False,
    }
    (HERE / "current-runtime-proof.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
