"""Bind independent positive/negative delivery and exact comparison audits."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

from audit_comparisons import PAIRS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = str(REPO / ".venv-cpu/bin/python")
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion", "original_alley_activity"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(value):
    return json.dumps(value, sort_keys=True, indent=2) + "\n"


def attempt(variant):
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    return scratch / ("compat-passenger-active-v2" if variant == "passenger_active_stop"
                      else "compat-" + variant + "-primary-v3")


def run(command, log):
    done = subprocess.run(command, cwd=REPO, env=os.environ.copy(),
                          capture_output=True, text=True)
    content = (done.stdout + done.stderr).rstrip()
    log.write_text(content + "\n" if content else "")
    return done


def prove():
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if REPO / ".runtime-work" not in scratch.parents:
        raise ValueError("audit scratch must be under .runtime-work")
    output_root = scratch / "independent-audits-v1"
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    plan_path = HERE / "case-plan.json"
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        variant = case_id.removeprefix(HERE.name + "__")
        positive_output = output_root / (variant + "-delivery.json")
        positive_output.unlink(missing_ok=True)
        command = [PYTHON, str(HERE / "delivery_audit.py"), "--case-id", case_id,
                   "--attempt", str(attempt(variant)), "--plan", str(plan_path),
                   "--output", str(positive_output)]
        log = HERE / ("cpu-delivery-" + variant + ".log")
        done = run(command, log)
        if done.returncode or len(json.loads(positive_output.read_text())["four_view_full_decode"]) != 4:
            raise ValueError("delivery positive audit failed: " + variant + " " + log.read_text()[-800:])
        missing = output_root / (variant + "-missing")
        if missing.exists():
            shutil.rmtree(missing)
        shutil.copytree(attempt(variant), missing)
        (missing / "original-attempt/activity.jsonl").unlink()
        negative_output = output_root / (variant + "-negative.json")
        negative_output.unlink(missing_ok=True)
        negative = command.copy()
        negative[negative.index("--attempt") + 1] = str(missing)
        negative[negative.index("--output") + 1] = str(negative_output)
        negative_log = HERE / ("cpu-delivery-" + variant + "-negative.log")
        failed = run(negative, negative_log)
        expected = "activity.jsonl"
        if failed.returncode == 0 or expected not in negative_log.read_text():
            raise ValueError("delivery missing-source negative not rejected: " + variant)
        entry["delivery_acceptance"] = {
            "case_id": case_id, "sets": ["full-test"], "checks": CHECKS,
            "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
            "command": shlex.join(command), "test_exit_code": 0,
            "test_log": log.name, "test_log_sha256": sha(log),
            "negative_command": shlex.join(negative), "negative_exit_code": failed.returncode,
            "negative_expected_error": expected,
            "negative_log": negative_log.name, "negative_log_sha256": sha(negative_log),
            "diagnostic_fixture": True, "physical_acceptance_claimed": False,
        }
        print("delivery", variant, "positive/negative passed", flush=True)
    manifest_path.write_text(dump(manifest))
    comparisons = []
    for comparison_id, members in PAIRS.items():
        output = output_root / (comparison_id + "-comparison.json")
        output.unlink(missing_ok=True)
        command = [PYTHON, str(HERE / "comparison_audit.py"), "--comparison", comparison_id,
                   "--comparison-id", HERE.name + "__" + comparison_id,
                   "--plan", str(plan_path)]
        for variant in members:
            command.extend(["--attempt", str(attempt(variant))])
        command.extend(["--output", str(output)])
        log = HERE / ("cpu-comparison-" + comparison_id + ".log")
        done = run(command, log)
        if done.returncode:
            raise ValueError("comparison audit failed: " + comparison_id + " " + log.read_text()[-800:])
        missing = output_root / (comparison_id + "-missing-first")
        if missing.exists():
            shutil.rmtree(missing)
        shutil.copytree(attempt(members[0]), missing)
        (missing / "original-attempt/activity.jsonl").unlink()
        negative_output = output_root / (comparison_id + "-negative.json")
        negative_output.unlink(missing_ok=True)
        negative = command.copy()
        negative[negative.index("--attempt") + 1] = str(missing)
        negative[negative.index("--output") + 1] = str(negative_output)
        negative_log = HERE / ("cpu-comparison-" + comparison_id + "-negative.log")
        failed = run(negative, negative_log)
        if failed.returncode == 0 or "activity.jsonl" not in negative_log.read_text():
            raise ValueError("comparison missing-source negative not rejected: " + comparison_id)
        comparisons.append({"comparison_id": comparison_id,
                            "case_ids": [HERE.name + "__" + name for name in members],
                            "audit": {"script": "comparison_audit.py", "script_sha256": sha(HERE / "comparison_audit.py"),
                                      "command": shlex.join(command), "test_exit_code": 0,
                                      "test_log": log.name, "test_log_sha256": sha(log),
                                      "negative_command": shlex.join(negative),
                                      "negative_exit_code": failed.returncode,
                                      "negative_log": negative_log.name,
                                      "negative_log_sha256": sha(negative_log),
                                      "result_sha256": sha(output), "diagnostic_fixture": True,
                                      "physical_acceptance_claimed": False}})
        print("comparison", comparison_id, "passed", flush=True)
    (HERE / "comparison-audits.json").write_text(dump({"format": "worker-comparison-audits",
                                                       "assignment_id": HERE.name, "comparisons": comparisons}))


if __name__ == "__main__":
    prove()
