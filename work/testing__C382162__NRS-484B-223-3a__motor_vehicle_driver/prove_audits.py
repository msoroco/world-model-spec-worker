"""Run independent delivery and fixed-context comparison CPU audits."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / ".venv-cpu/bin/python"
SCRATCH = REPO / ".runtime-work/c382162-owner"
PLAN = HERE / "case-plan.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def command_run(command, log, positive=True):
    done = subprocess.run(command, cwd=REPO, env=os.environ, text=True,
                          capture_output=True)
    log.write_text((done.stdout + done.stderr).rstrip() + "\n")
    if positive and done.returncode:
        raise ValueError("CPU audit failed: " + " ".join(command) + "\n" + done.stderr[-1500:])
    if not positive and done.returncode == 0:
        raise ValueError("negative audit accepted missing original source")
    return done.returncode


def prove():
    proof_dir = SCRATCH / "delivery-proofs"
    proof_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        name = case.removeprefix(HERE.name + "__")
        attempt = SCRATCH / ("compat-full3-" + name + "-primary")
        output = proof_dir / (name + "-audit.json")
        command = [str(PYTHON), str(HERE / "delivery_audit.py"), "--case-id", case,
                   "--attempt", str(attempt), "--plan", str(PLAN),
                   "--output", str(output)]
        log = HERE / ("cpu-delivery-" + name + ".log")
        command_run(command, log)
        receipt = json.loads(output.read_text())
        if not receipt["source_video_join"] or receipt["capture_frames"] != 9 or \
                len(receipt["four_view_full_decode"]) != 4:
            raise ValueError("independent diagnostic delivery receipt incomplete")
        missing = proof_dir / (name + "-missing")
        (missing / "native").mkdir(parents=True, exist_ok=True)
        for source in ("config.json", "construction.json", "pre-entry-intent.json"):
            shutil.copyfile(attempt / source, missing / source)
        for source in ("inventory.json", "site.json"):
            shutil.copyfile(attempt / "native" / source, missing / "native" / source)
        negative = command.copy()
        negative[negative.index("--attempt") + 1] = str(missing)
        negative[negative.index("--output") + 1] = str(proof_dir / (name + "-negative.json"))
        neglog = HERE / ("cpu-delivery-" + name + "-negative.log")
        negative_exit = command_run(negative, neglog, positive=False)
        expected = "Missing required source: native/history.json"
        if expected not in neglog.read_text():
            raise ValueError("missing original route source did not reject")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
            "command": " ".join(command), "test_exit_code": 0,
            "test_log": log.name, "test_log_sha256": sha(log),
            "negative_command": " ".join(negative), "negative_exit_code": negative_exit,
            "negative_expected_error": expected, "negative_log": neglog.name,
            "negative_log_sha256": sha(neglog), "diagnostic_fixture": True,
            "physical_acceptance_claimed": False}
        print("independent delivery", name, "passed", flush=True)
    comparisons = json.loads(PLAN.read_text())["comparisons"]
    for row in comparisons:
        name = row["comparison_id"]
        case_id = HERE.name + "__" + name
        attempts = [SCRATCH / ("compat-full3-" + case.removeprefix(HERE.name + "__") + "-primary")
                    for case in row["case_ids"]]
        output = proof_dir / (name + "-comparison.json")
        command = [str(PYTHON), str(HERE / "comparison_audit.py")]
        for attempt in attempts:
            command.extend(("--attempt", str(attempt)))
        command.extend(("--comparison", name, "--comparison-id", case_id,
                        "--plan", str(PLAN), "--output", str(output)))
        log = HERE / ("cpu-comparison-" + name + ".log")
        command_run(command, log)
        print("independent comparison", name, "passed", flush=True)
    write(manifest_path, manifest)


if __name__ == "__main__":
    prove()
