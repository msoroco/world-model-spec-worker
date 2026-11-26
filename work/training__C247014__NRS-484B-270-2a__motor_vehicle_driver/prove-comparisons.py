"""Retain independent paired-source positives and non-target mutation rejections."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRIPT = HERE / "comparison-audit.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipts = []
    folder = HERE / "proofs" / "comparisons"
    folder.mkdir(parents=True, exist_ok=True)
    scratch = REPO / ".runtime-work" / "c247014-resume-v5"
    for pair in ("witness", "exception", "unsafe_available"):
        result = folder / (pair + "-positive.json")
        command = [sys.executable, "-B", str(SCRIPT), "--pair", pair,
                   "--output", str(result)]
        run = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=30)
        if run.returncode or run.stderr:
            raise ValueError("Controlled comparison positive failed: " + pair + " " + run.stderr)
        positive = json.loads(result.read_text())
        if (positive["frames"] != 600 or positive["deliberate_difference"] not in
                ("requested_lane_move", "left_lane_occupant_plan", "closing_left_vehicle_context") or
                positive["original_native_observed"]):
            raise ValueError("Controlled comparison made an unsupported claim")
        log = folder / (pair + "-positive.log")
        log.write_text(run.stdout)
        negative = [sys.executable, "-B", str(SCRIPT), "--pair", pair,
                    "--output", str(scratch / ("comparison-" + pair + "-negative.json")),
                    "--negative"]
        run = subprocess.run(negative, cwd=REPO, capture_output=True, text=True, timeout=30)
        negative_log = folder / (pair + "-negative.log")
        negative_log.write_text(run.stdout + run.stderr)
        if run.returncode == 0 or "Controlled non-target source differs at frame 75" not in negative_log.read_text():
            raise ValueError("Controlled comparison missing non-target source rejection")
        receipts.append({"pair": pair, "positive": str(result.relative_to(HERE)),
                         "positive_sha256": sha(result), "positive_log": str(log.relative_to(HERE)),
                         "positive_log_sha256": sha(log), "negative_log": str(negative_log.relative_to(HERE)),
                         "negative_log_sha256": sha(negative_log),
                         "negative_expected_error": "Controlled non-target source differs at frame 75"})
    report = {"format": "c247014-controlled-comparison-proof-v1",
              "script": str(SCRIPT.relative_to(HERE)), "script_sha256": sha(SCRIPT),
              "pairs": receipts, "synthetic_fixture": True,
              "original_native_observed": False, "legal_judgment": None}
    path = folder / "receipt.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"pairs": len(receipts), "receipt_sha256": sha(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
