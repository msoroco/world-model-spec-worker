"""Bind independent four-camera source audits and tamper rejections per case."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / ".runtime-work/c202480-owner/delivery"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
    script = HERE / "delivery_probe.py"
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        outcomes = []
        for negative in (False, True):
            label = "negative" if negative else "positive"
            output = ROOT / (suffix + "-" + label)
            if output.exists():
                shutil.rmtree(output)
            command = [str(REPO / ".venv-cpu/bin/python"), str(script),
                       "--case", entry["case_id"], "--output", str(output)]
            if negative:
                command.append("--negative")
            done = subprocess.run(command, cwd=REPO,
                                  env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                  capture_output=True, text=True, timeout=180)
            log = HERE / ("delivery-" + suffix + "-" + label + ".log")
            log.write_text((done.stdout + done.stderr).rstrip("\n") + "\n")
            expected = "sealed original source changed: native-stop-device.json"
            if negative:
                if done.returncode == 0 or expected not in log.read_text():
                    raise ValueError("sealed-source negative failed: " + suffix)
            elif done.returncode or '"diagnostic_audit_test_passed": true' not in done.stdout:
                raise ValueError("independent audit failed: " + suffix + done.stderr[-500:])
            outcomes.append({"command": " ".join(command), "exit_code": done.returncode,
                             "log": log.name, "log_sha256": sha(log)})
        entry["delivery_acceptance"] = {
            "case_id": entry["case_id"],
            "sets": assignment["selection_targets"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "scope": "synthetic diagnostic exercises audit; actual Native physical acceptance remains pending",
            "script": script.name, "script_sha256": sha(script),
            "command": outcomes[0]["command"],
            "test_exit_code": outcomes[0]["exit_code"],
            "test_log": outcomes[0]["log"],
            "test_log_sha256": outcomes[0]["log_sha256"],
            "negative_command": outcomes[1]["command"],
            "negative_exit_code": outcomes[1]["exit_code"],
            "negative_expected_error": "sealed original source changed: native-stop-device.json",
            "negative_log": outcomes[1]["log"],
            "negative_log_sha256": outcomes[1]["log_sha256"]}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(suffix, "independent delivery audit and tamper rejection passed", flush=True)


if __name__ == "__main__":
    main()
