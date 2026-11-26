"""Bind exact positive and source-mutation CPU audit fixtures."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    scratch = REPO / ".runtime-work/c150088-nov26/audit-proofs-v1"
    scratch.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch),
                       PYTHONDONTWRITEBYTECODE="1")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        evidence = {}
        for kind in ("positive", "negative"):
            command = [str(REPO / ".venv-cpu/bin/python"), str(ROOT / "audit_probe.py"),
                       "--case", entry["case_id"], "--output", str(scratch / (suffix + "-" + kind))]
            if kind == "negative":
                command.append("--negative")
            completed = subprocess.run(command, cwd=REPO, env=environment,
                                       capture_output=True, text=True)
            log = ROOT / ("audit-" + suffix + "-" + kind + ".log")
            log.write_text((completed.stdout + completed.stderr).rstrip() + "\n", encoding="utf-8")
            if completed.returncode != (0 if kind == "positive" else 1):
                raise RuntimeError(suffix + " " + kind + ": " + log.read_text()[-1300:])
            evidence[kind] = {"command": " ".join(command), "exit_code": completed.returncode,
                              "log": log.name, "log_sha256": sha(log)}
        if "sealed original missing or changed" not in (ROOT / evidence["negative"]["log"]).read_text():
            raise ValueError("missing exact source-mutation rejection")
        entry["delivery_acceptance"] = {"case_id": entry["case_id"], "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(ROOT / "delivery_audit.py"),
            "command": evidence["positive"]["command"], "test_exit_code": 0,
            "test_log": evidence["positive"]["log"],
            "test_log_sha256": evidence["positive"]["log_sha256"],
            "negative_command": evidence["negative"]["command"],
            "negative_exit_code": evidence["negative"]["exit_code"],
            "negative_expected_error": "sealed original missing or changed",
            "negative_log": evidence["negative"]["log"],
            "negative_log_sha256": evidence["negative"]["log_sha256"]}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(suffix, "passed", flush=True)


if __name__ == "__main__":
    main()
