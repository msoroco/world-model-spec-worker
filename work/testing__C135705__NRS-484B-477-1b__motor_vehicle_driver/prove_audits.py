"""Run positive/negative delivery and four independent comparison audits."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = str(REPO / ".venv-cpu/bin/python")
SCRATCH = REPO / ".runtime-work/c135705-owner/audits"
MANIFEST = HERE / "execution-manifest.json"
PLAN = HERE / "case-plan.json"
CHECKS = ["native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion",
          "original_width_source"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def run(command):
    return subprocess.run(command, cwd=REPO, env=os.environ,
                          capture_output=True, text=True)


def log(name, done):
    path = HERE / name
    content = (done.stdout + done.stderr).rstrip()
    path.write_text(content + "\n" if content else "")
    return path


def prove():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        name = case_id.removeprefix(HERE.name + "__")
        attempt = REPO / ".runtime-work/c135705-owner" / ("current/compat-" + name + "-primary")
        output = SCRATCH / (name + "-delivery.json")
        command = [PYTHON, str(HERE / "delivery_audit.py"),
                   "--case-id", case_id, "--attempt", str(attempt),
                   "--plan", str(PLAN), "--output", str(output)]
        done = run(command)
        positive_log = log("cpu-delivery-" + name + ".log", done)
        if done.returncode or not json.loads(output.read_text())["four_view_full_decode"]:
            raise RuntimeError("positive independent delivery audit failed: " + positive_log.read_text()[-1500:])
        missing = SCRATCH / (name + "-missing")
        if missing.exists():
            shutil.rmtree(missing)
        shutil.copytree(attempt, missing)
        (missing / "original-attempt/width_history.json").unlink()
        negative_output = SCRATCH / (name + "-negative.json")
        negative = command.copy()
        negative[negative.index("--attempt") + 1] = str(missing)
        negative[negative.index("--output") + 1] = str(negative_output)
        failed = run(negative)
        negative_log = log("cpu-delivery-" + name + "-negative.log", failed)
        expected = "original width_history packet missing"
        if failed.returncode == 0 or expected not in negative_log.read_text():
            raise RuntimeError("negative independent delivery audit did not reject missing original: " + name)
        entry["delivery_acceptance"] = {
            "case_id": case_id, "sets": ["full-test"],
            "checks": CHECKS, "script": "delivery_audit.py",
            "script_sha256": sha(HERE / "delivery_audit.py"),
            "command": " ".join(command), "test_exit_code": 0,
            "test_log": positive_log.name, "test_log_sha256": sha(positive_log),
            "negative_command": " ".join(negative),
            "negative_exit_code": failed.returncode,
            "negative_expected_error": expected,
            "negative_log": negative_log.name,
            "negative_log_sha256": sha(negative_log),
            "diagnostic_fixture": True, "physical_acceptance_claimed": False}
        print("delivery positive+negative", name, "passed", flush=True)
    write(MANIFEST, manifest)
    plan = json.loads(PLAN.read_text())
    comparison_receipts = []
    for comparison in plan["comparisons"]:
        name = comparison["comparison_id"]
        attempts = [REPO / ".runtime-work/c135705-owner" /
                    ("current/compat-" + cid.removeprefix(HERE.name + "__") + "-primary")
                    for cid in comparison["case_ids"]]
        output = SCRATCH / (name + "-comparison.json")
        command = [PYTHON, str(HERE / "comparison_audit.py"),
                   "--comparison", name,
                   "--comparison-id", HERE.name + "__" + name,
                   "--plan", str(PLAN)]
        for attempt in attempts:
            command.extend(["--attempt", str(attempt)])
        command.extend(["--output", str(output)])
        done = run(command)
        audit_log = log("cpu-comparison-" + name + ".log", done)
        if done.returncode:
            raise RuntimeError("independent comparison audit failed: " + audit_log.read_text()[-1500:])
        comparison_receipts.append({"comparison_id": name,
            "case_ids": comparison["case_ids"],
            "audit": {
            "script": "comparison_audit.py", "script_sha256": sha(HERE / "comparison_audit.py"),
            "command": " ".join(command), "test_exit_code": 0,
            "test_log": audit_log.name, "test_log_sha256": sha(audit_log),
            "result_sha256": sha(output), "diagnostic_fixture": True,
            "physical_acceptance_claimed": False}})
        print("comparison", name, "passed", flush=True)
    write(HERE / "comparison-audits.json", {
        "format": "worker-comparison-audits", "assignment_id": HERE.name,
        "comparisons": comparison_receipts})


if __name__ == "__main__":
    prove()
