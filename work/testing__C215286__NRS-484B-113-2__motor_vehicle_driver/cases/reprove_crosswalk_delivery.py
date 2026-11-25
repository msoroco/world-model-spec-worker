"""Rebind two full-duration crosswalk delivery audits to current constructions."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]
MANIFEST = PACKAGE / "execution-manifest.json"
SCRIPT = PACKAGE / "delivery_audit.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def run():
    output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not output_root or not Path(output_root).resolve().is_relative_to(REPO / ".runtime-work"):
        raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    manifest = json.loads(MANIFEST.read_text())
    for label, entry in zip(("over", "short"), manifest["cases"][:2]):
        case_id = entry["case_id"]
        proof = entry["delivery_acceptance"]
        for mode, expected in (("positive", 0), ("negative", 1)):
            cmd = [sys.executable, str(SCRIPT), "--case", case_id, "--mode", mode]
            log = PACKAGE / "cases" / (label + "-current-runtime-delivery-" + mode + ".log")
            with log.open("w") as stream:
                result = subprocess.run(cmd, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=600, check=False)
            if (result.returncode == 0) != (expected == 0):
                raise RuntimeError(label + " " + mode + " delivery audit exit differed")
            if mode == "negative" and "Original source changed: video_frames.jsonl" not in log.read_text():
                raise ValueError("Changed original frame map was not rejected")
            if mode == "positive":
                receipt = json.loads(log.read_text())
                if receipt.get("frames") != 900 or receipt.get("software_audit_passed") is not True:
                    raise ValueError("Full-duration software delivery audit incomplete")
            command = "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c215286-delivery-audit-current " + " ".join(cmd)
            if mode == "positive":
                proof.update(command=command, test_exit_code=0, test_log="cases/" + log.name,
                             test_log_sha256=sha(log))
            else:
                proof.update(negative_command=command, negative_exit_code=result.returncode,
                             negative_log="cases/" + log.name, negative_log_sha256=sha(log))
        proof["script_sha256"] = sha(SCRIPT)
        proof["auditor_sha256"] = sha(SCRIPT)
        write(MANIFEST, manifest)
        print(label, "current 900-frame delivery positive and changed-source negative passed", flush=True)


if __name__ == "__main__":
    run()
