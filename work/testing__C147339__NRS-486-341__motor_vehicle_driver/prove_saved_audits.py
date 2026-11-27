"""Run exact positive/negative saved-source and comparison audits."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c147339-audits"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run(command, log, expected_code, expected_text):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "pipeline"))
    completed = subprocess.run(command, cwd=REPO, env=environment,
                               capture_output=True, text=True)
    content = (completed.stdout + completed.stderr).rstrip() + "\n"
    log.write_text(content, encoding="utf-8")
    if completed.returncode != expected_code or expected_text not in content:
        raise ValueError("Saved audit differed: " + str(log) + " code=" + str(completed.returncode))
    return sha(log)


def attempt_for(suffix):
    if suffix == "motorcycle_adjacent_clear":
        return REPO / ".runtime-work/c147339-compat-third"
    return REPO / (".runtime-work/c147339-compat-batch-" + suffix + "-primary")


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    script = ROOT / "delivery_audit.py"
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        suffix = cid.split("__")[-1]
        attempt = attempt_for(suffix)
        if not (attempt / "compatibility.json").is_file():
            raise ValueError("Missing exact compatibility source: " + cid)
        positive = [sys.executable, str(script), "--attempt", str(attempt), "--case", cid]
        negative = positive + ["--require-original"]
        positive_log = ROOT / ("cpu-delivery-positive-" + suffix + ".log")
        negative_log = ROOT / ("cpu-delivery-negative-" + suffix + ".log")
        positive_hash = run(positive, positive_log, 0, '"native_source": false')
        negative_hash = run(negative, negative_log, 1,
                            "Diagnostic source cannot satisfy original Native delivery")
        entry["delivery_acceptance"] = {
            "case_id": cid, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": script.name, "script_sha256": sha(script),
            "command": " ".join(positive), "negative_command": " ".join(negative),
            "test_exit_code": 0, "negative_exit_code": 1,
            "negative_expected_error": "Diagnostic source cannot satisfy original Native delivery",
            "test_log": positive_log.name, "test_log_sha256": positive_hash,
            "negative_log": negative_log.name, "negative_log_sha256": negative_hash,
            "scope": "CPU diagnostic integrity and original-only rejection; Native visual and physical review awaits GPU"}
        print(suffix, "delivery positive/negative passed", flush=True)
    write(manifest_path, manifest)
    plan = json.loads((ROOT / "case-plan.json").read_text())
    specs = []
    script = ROOT / "comparison_audit.py"
    for item in plan["comparisons"]:
        left_id, right_id = item["case_ids"]
        left, right = attempt_for(left_id.split("__")[-1]), attempt_for(right_id.split("__")[-1])
        comparison = item["comparison_id"]
        positive = [sys.executable, str(script), "--comparison", comparison,
                    "--left", str(left), "--right", str(right)]
        negative = [sys.executable, str(script), "--comparison", comparison,
                    "--left", str(left), "--right", str(left)]
        positive_log = ROOT / ("cpu-comparison-positive-" + comparison + ".log")
        negative_log = ROOT / ("cpu-comparison-negative-" + comparison + ".log")
        positive_hash = run(positive, positive_log, 0, '"fixed_conditions_checked": true')
        negative[negative.index("--right") + 1] = str(left)
        negative_hash = run(negative, negative_log, 1, "Exact attempt identity")
        specs.append({"comparison_id": comparison, "case_ids": item["case_ids"],
                      "script": script.name, "script_sha256": sha(script),
                      "command": " ".join(positive), "negative_command": " ".join(negative),
                      "test_exit_code": 0, "negative_exit_code": 1,
                      "positive_log": positive_log.name, "positive_log_sha256": positive_hash,
                      "negative_log": negative_log.name, "negative_log_sha256": negative_hash,
                      "scope": "Source-bound diagnostic contrast; no legal verdict"})
        print(comparison, "comparison positive/negative passed", flush=True)
    write(ROOT / "comparison-audit-specs.json", {"format": "worker-comparison-audit-specs",
                                                 "assignment_id": ROOT.name, "comparisons": specs})


if __name__ == "__main__":
    main()
