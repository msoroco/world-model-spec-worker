"""Run and bind positive/negative structure delivery diagnostics."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from structure_delivery_audit import ERROR


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRIPT = HERE / "structure_delivery_audit.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    count = 0
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        if not suffix.startswith(("bridge_", "viaduct_")):
            continue
        case = entry["case_id"]
        stem = HERE / "selected-proofs" / suffix
        outputs = []
        for diagnostic, label in ((True, "delivery-audit"), (False, "delivery-negative")):
            args = [sys.executable, "-B", str(SCRIPT), "--case", case]
            if diagnostic:
                args.append("--diagnostic")
            result = subprocess.run(args, capture_output=True, text=True)
            log = Path(str(stem) + "-" + label + ".log")
            log.write_text((result.stdout + result.stderr).rstrip() + "\n")
            if diagnostic and result.returncode != 0:
                raise ValueError("Positive structure delivery audit failed: " + suffix)
            if not diagnostic and (result.returncode == 0 or ERROR not in log.read_text()):
                raise ValueError("Original structure acceptance was not rejected: " + suffix)
            outputs.append((result.returncode, log))
        positive, negative = outputs
        command = ".venv-cpu/bin/python -B work/" + HERE.name + "/structure_delivery_audit.py --case " + case
        entry["delivery_acceptance"] = {"case_id": case, "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": SCRIPT.name, "script_sha256": sha(SCRIPT),
            "command": command + " --diagnostic", "negative_command": command,
            "test_exit_code": positive[0], "negative_exit_code": negative[0],
            "negative_expected_error": ERROR,
            "test_log": "selected-proofs/" + positive[1].name,
            "test_log_sha256": sha(positive[1]),
            "negative_log": "selected-proofs/" + negative[1].name,
            "negative_log_sha256": sha(negative[1]),
            "scope": "CPU diagnostic join and required rejection; original Native physical and legal acceptance pending"}
        count += 1
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return {"cases": count, "manifest_sha256": sha(path)}


if __name__ == "__main__":
    print(json.dumps(run()))
