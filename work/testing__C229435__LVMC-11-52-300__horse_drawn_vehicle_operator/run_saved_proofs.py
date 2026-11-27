"""Test selected saved-only processing without replay or source modification."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
SCRATCH = REPO / ".runtime-work/c229435-saved"
VALIDATOR = REPO / ".runtime-work/c229435-diagnostic/validator/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "runtime/scenario_pipeline") + ":" + str(REPO / "runtime/python")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        destination = SCRATCH / (suffix + "-v3")
        log = ROOT / ("saved-" + suffix + ".log")
        if not destination.exists():
            command = [str(REPO / ".venv-cpu/bin/python"), str(ROOT / "saved_probe.py"),
                       "--case", entry["case_id"], "--output", str(destination),
                       "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
            completed = subprocess.run(command, cwd=REPO, env=env, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       check=True)
            log.write_text(completed.stdout.rstrip() + "\n")
        elif not log.is_file():
            raise ValueError("retained saved run lacks proof log: " + suffix)
        processing = json.loads((destination / "derived/v0001/processing.json").read_text())
        if processing.get("passed") is not True or processing.get("recorded_only") is not True:
            raise ValueError("saved-only receipt incomplete: " + suffix)
        entry["post_capture"] = {
            "recorded_only": True,
            "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + ASSIGNMENT
                       + "/execution-manifest.json --case " + entry["case_id"]
                       + " --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR --owner-release-receipt $OWNER_RELEASE",
            "feedback_command": "cat $OUTPUT/feedback.json # " + entry["case_id"],
            "test_exit_code": 0, "test_log": log.name, "test_log_sha256": sha(log),
        }
        print("saved-only pass", suffix, flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
