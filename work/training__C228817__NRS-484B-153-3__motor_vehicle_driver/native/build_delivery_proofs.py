"""Run independent exact-case delivery auditor positive and negative CPU tests."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


folder = Path(__file__).resolve().parents[1]
manifest_path = folder / "execution-manifest.json"
manifest = json.loads(manifest_path.read_text())
script = folder / "delivery_audit.py"
root = Path(__file__).resolve().parents[3]
env = dict(os.environ)
env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(root / ".runtime-work/c228817-resume")
env["TMPDIR"] = str(root / ".runtime-work")
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["PYTHONPATH"] = str(root / "runtime/scenario_pipeline") + ":" + str(root / "runtime/python")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


for number, entry in enumerate(manifest["cases"], 1):
    case = entry["case_id"]
    proof_dir = folder / "native/proofs" / f"probe-{number}/delivery"
    proof_dir.mkdir(exist_ok=True)
    base = [sys.executable, "-B", str(script), "--case", case, "--selftest"]
    positive = subprocess.run(base, cwd=root, env=env, capture_output=True, text=True)
    negative = subprocess.run(base + ["--negative-fixture"], cwd=root, env=env,
                              capture_output=True, text=True)
    if positive.returncode != 0 or negative.returncode == 0 or \
            "Synthetic fixture cannot establish original Native delivery" not in negative.stderr:
        raise ValueError("Independent delivery CPU boundary failed for " + case)
    positive_log = proof_dir / "positive.log"
    negative_log = proof_dir / "negative.log"
    positive_log.write_text(positive.stdout.rstrip() + "\n")
    negative_log.write_text(negative.stderr.rstrip() + "\n")
    entry["delivery_acceptance"] = {
        "case_id": case, "sets": ["full-train"],
        "checks": ["native_source", "all_participants", "time_join",
                   "full_video_decode", "actual_pixels", "physical_completion"],
        "script": str(script.relative_to(folder)), "script_sha256": sha(script),
        "command": " ".join(base), "test_exit_code": positive.returncode,
        "test_log": str(positive_log.relative_to(folder)),
        "test_log_sha256": sha(positive_log),
        "negative_command": " ".join(base + ["--negative-fixture"]),
        "negative_exit_code": negative.returncode,
        "negative_expected_error": "Synthetic fixture cannot establish original Native delivery",
        "negative_log": str(negative_log.relative_to(folder)),
        "negative_log_sha256": sha(negative_log)}
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print("four independent exact-case delivery CPU proof pairs bound")
