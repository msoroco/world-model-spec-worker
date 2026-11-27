"""Retain positive and missing-classification delivery protocol checks."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
SAVED = REPO / ".runtime-work/c229435-saved"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "runtime/scenario_pipeline") + ":" + str(REPO / "runtime/python")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        root = SAVED / (suffix + "-v3")
        if not (root / "derived/v0001/processing.json").is_file():
            raise ValueError("saved processing proof required before delivery protocol")
        logs = {}
        for mode, expected in (("positive", 0), ("missing_source", 2)):
            log = ROOT / ("delivery-" + suffix + "-" + mode + ".log")
            command = [str(REPO / ".venv-cpu/bin/python"), str(ROOT / "delivery_probe.py"),
                       "--case", entry["case_id"], "--saved-root", str(root), "--mode", mode]
            result = subprocess.run(command, cwd=REPO, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != expected:
                raise ValueError("delivery protocol " + mode + " failed: " + result.stdout[-1000:])
            log.write_text(result.stdout.rstrip() + "\n")
            logs[mode] = log
        entry["delivery_acceptance"] = {
            "case_id": entry["case_id"], "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(ROOT / "delivery_audit.py"),
            "command": "PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/" + ASSIGNMENT
                       + "/delivery_probe.py --case " + entry["case_id"]
                       + " --saved-root .runtime-work/c229435-saved/" + suffix + "-v3 --mode positive",
            "test_exit_code": 0, "test_log": logs["positive"].name,
            "test_log_sha256": sha(logs["positive"]),
            "negative_command": "PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/"
                                + ASSIGNMENT + "/delivery_probe.py --case " + entry["case_id"]
                                + " --saved-root .runtime-work/c229435-saved/" + suffix + "-v3 --mode missing_source",
            "negative_exit_code": 2,
            "negative_expected_error": "sealed original missing or changed: classification.json",
            "negative_log": logs["missing_source"].name,
            "negative_log_sha256": sha(logs["missing_source"]),
        }
        print("delivery protocol pass", suffix, flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
