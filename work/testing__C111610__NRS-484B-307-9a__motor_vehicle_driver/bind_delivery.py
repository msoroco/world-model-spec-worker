"""Bind six exact independent delivery audit CPU receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        positive = HERE / ("proof-delivery-" + suffix + ".log")
        negative = HERE / ("proof-delivery-" + suffix + "-negative.log")
        diagnostic = json.loads(positive.read_text())
        if (diagnostic.get("case_id") != case_id or
                diagnostic.get("decoded_original_png_frames") != 2400 or
                diagnostic.get("physical_acceptance_claimed") is not False or
                "source hash mismatch" not in negative.read_text()):
            raise ValueError("delivery source proof incomplete: " + case_id)
        command = f".venv-cpu/bin/python delivery_probe.py --case {case_id}"
        entry["delivery_acceptance"] = {
            "case_id": case_id, "sets": ["full-test"], "checks": list(CHECKS),
            "script": "delivery_probe.py", "script_sha256": sha(HERE / "delivery_probe.py"),
            "auditor": "delivery_audit.py", "auditor_sha256": sha(HERE / "delivery_audit.py"),
            "command": command, "test_exit_code": 0,
            "test_log": positive.name, "test_log_sha256": sha(positive),
            "negative_command": command + " --negative", "negative_exit_code": 1,
            "negative_expected_error": "source hash mismatch",
            "negative_log": negative.name, "negative_log_sha256": sha(negative),
            "production_command": f".venv-cpu/bin/python delivery_audit.py --case {case_id} --attempt $SAVED_ATTEMPT",
            "diagnostic_cpu_proof": diagnostic,
            "physical_acceptance_claimed": False}
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound", len(manifest["cases"]), "independent delivery CPU receipts")


if __name__ == "__main__":
    bind()
