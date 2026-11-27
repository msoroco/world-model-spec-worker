"""Bind exact-case diagnostic delivery source-audit positive/negative tests."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c213645-owner"
MANIFEST = HERE / "execution-manifest.json"
SCRIPT = HERE / "prove_delivery.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


manifest = json.loads(MANIFEST.read_text())
for entry in manifest["cases"]:
    name = entry["case_id"].split("__")[-1]
    results = {}
    for kind in ("positive", "negative"):
        command = [sys.executable, str(SCRIPT), "--case", entry["case_id"]]
        if kind == "negative":
            command.append("--negative")
        env = dict(os.environ)
        env.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH / "tmp"),
                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "pipeline"))
        process = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
        log = HERE / ("cpu-delivery-" + name + "-" + kind + ".log")
        log.write_text((process.stdout + process.stderr).rstrip() + "\n")
        results[kind] = {"command": " ".join(command), "exit_code": process.returncode,
                         "log": log.name, "log_sha256": sha(log)}
    expected = "original camera source absent or changed: overview"
    if results["positive"]["exit_code"] != 0 or results["negative"]["exit_code"] == 0 or expected not in (HERE / results["negative"]["log"]).read_text():
        raise ValueError("exact delivery diagnostic positive/negative differs: " + name)
    entry["delivery_acceptance"] = {
        "case_id": entry["case_id"], "sets": ["full-test"],
        "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                   "actual_pixels", "physical_completion"],
        "script": SCRIPT.name, "script_sha256": sha(SCRIPT),
        "command": results["positive"]["command"], "test_exit_code": 0,
        "test_log": results["positive"]["log"], "test_log_sha256": results["positive"]["log_sha256"],
        "negative_command": results["negative"]["command"],
        "negative_exit_code": results["negative"]["exit_code"],
        "negative_expected_error": expected,
        "negative_log": results["negative"]["log"],
        "negative_log_sha256": results["negative"]["log_sha256"],
        "scope": "synthetic CPU source-audit proof; original pixel and physical acceptance are local gates",
    }
    write(MANIFEST, manifest)
    print(name, "positive and missing-camera negative passed", flush=True)
