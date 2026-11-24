"""Bind exact selected delivery-audit CPU proofs to the execution manifest."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "execution-manifest.json"
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


data = json.loads(MANIFEST.read_text())
for entry in data["cases"]:
    case = entry["case_id"]
    suffix = case.split("__")[-1]
    positive = suffix + "-acceptance-positive.log"
    negative = suffix + "-acceptance-negative.log"
    proof = json.loads((HERE / positive).read_text())
    rejection = (HERE / negative).read_text()
    assert proof["case_id"] == case and proof["diagnostic_fixture"] is True
    assert proof["native_or_pixel_acceptance_claimed"] is False
    assert "ValueError: Physical completion source changed: lane_history.jsonl" in rejection
    base = ".venv-cpu/bin/python work/" + HERE.name + "/prove_delivery_acceptance.py --case " + case
    entry["delivery_acceptance"] = {
        "case_id": case,
        "sets": ["demo-test", "full-test"],
        "checks": CHECKS,
        "script": "delivery_acceptance.py",
        "script_sha256": digest(HERE / "delivery_acceptance.py"),
        "command": base + " --mode positive",
        "negative_command": base + " --mode negative",
        "test_exit_code": 0,
        "negative_exit_code": 1,
        "negative_expected_error": "ValueError: Physical completion source changed: lane_history.jsonl",
        "test_log": positive,
        "test_log_sha256": digest(HERE / positive),
        "negative_log": negative,
        "negative_log_sha256": digest(HERE / negative),
        "scope": "CPU synthetic source joins and tamper rejection; Native and independent pixel review remain pending",
    }
MANIFEST.write_text(json.dumps(data, indent=2) + "\n")
print("bound", len(data["cases"]), "exact delivery acceptance contracts")
