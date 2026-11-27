"""Bind positive/negative CPU checks of the independent saved-source auditor."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
MANIFEST = PACKAGE / "execution-manifest.draft.json"
SCRIPT = PACKAGE / "prove_delivery_audit.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(PACKAGE.name + "__")
        command = [sys.executable, str(SCRIPT), case_id]
        runs = []
        for negative in (False, True):
            args = command + (["--negative"] if negative else [])
            run = subprocess.run(args, cwd=REPO, text=True, capture_output=True)
            log = PACKAGE / f"proof-delivery-{suffix}-{'negative' if negative else 'positive'}.log"
            log.write_text((run.stdout + run.stderr).rstrip() + "\n")
            runs.append((run.returncode, log, " ".join(args)))
        positive, negative = runs
        expected = "original saved acquisition required for physical review"
        if positive[0] != 0 or negative[0] == 0 or expected not in negative[1].read_text():
            raise ValueError("delivery audit CPU proof failed: " + suffix)
        entry["delivery_acceptance"] = {
            "case_id": case_id, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": SCRIPT.name, "script_sha256": sha(SCRIPT),
            "command": positive[2], "test_exit_code": 0,
            "test_log": positive[1].name, "test_log_sha256": sha(positive[1]),
            "negative_command": negative[2], "negative_exit_code": negative[0],
            "negative_expected_error": expected,
            "negative_log": negative[1].name, "negative_log_sha256": sha(negative[1]),
            "scope": "Diagnostic CPU source-checker proof only; original pixel and physical review pending"}
    write(MANIFEST, manifest)
    print("bound", len(manifest["cases"]), "delivery audit CPU proof pairs")


if __name__ == "__main__":
    main()
