"""Prove all six portable original-comparison commands on diagnostic fixtures."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = REPO / ".runtime-work" / "c111125-9b-owner" / "saved-v1"
SCRATCH = REPO / ".runtime-work" / "c111125-9b-original-comparison-proof"
PAIRS = {
    "complete_cycle_count": ("two_cycles_clear", "one_cycle_entry"),
    "complete_cycle_count_above": ("two_cycles_clear", "three_cycles_clear"),
    "stopping_event": ("two_cycles_clear", "rolling_entry"),
    "causal_record": ("two_cycles_clear", "no_causal_record"),
    "crosswalk_yield": ("two_cycles_clear", "pedestrian_crosswalk"),
    "intersection_yield": ("two_cycles_clear", "lawful_traffic"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(suffix):
    return BASE / ("saved-attempt-post-" + suffix)


def invoke(name, first, second, output, diagnostic=True):
    command = [sys.executable, str(HERE / "original_comparison_audit.py"),
               "--comparison", name, "--first-attempt", str(first),
               "--second-attempt", str(second), "--output", str(output)]
    if diagnostic:
        command.append("--diagnostic-fixture")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work" / "c111125-9b-output"))
    return subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True,
                          timeout=180)


def altered(name):
    target = SCRATCH / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(fixture("two_cycles_clear"), target)
    return target


def reject(label, first, expected, diagnostic=True):
    output = SCRATCH / (label + "-report.json")
    output.unlink(missing_ok=True)
    process = invoke("complete_cycle_count", first, fixture("one_cycle_entry"),
                     output, diagnostic)
    if process.returncode == 0 or expected not in process.stderr or output.exists():
        raise AssertionError(label + " did not reject: " + process.stderr[-800:])
    log = HERE / ("original-comparison-negative-" + label + ".log")
    log.write_text(process.stderr)
    return {"rejected": True, "reason": expected, "log": log.name,
            "log_sha256": sha(log)}


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    proof = {"format": "c111125-original-comparison-cli-proof", "diagnostic_only": True,
             "physical_acceptance": False, "legal_verdict": None, "comparisons": {}}
    for name, (left, right) in PAIRS.items():
        output = SCRATCH / (name + ".json")
        output.unlink(missing_ok=True)
        run = invoke(name, fixture(left), fixture(right), output)
        if run.returncode or not output.is_file():
            raise AssertionError(name + " positive failed: " + run.stderr[-800:])
        report = json.loads(output.read_text())
        if not report["passed"] or not report["diagnostic_only"] or report["case_ids"] != [
                HERE.name + "__" + left, HERE.name + "__" + right]:
            raise AssertionError(name + " exact diagnostic report differs")
        proof["comparisons"][name] = {"passed": True, "report_sha256": sha(output),
            "case_ids": report["case_ids"], "fixed_conditions_checked": report["fixed_conditions_checked"]}
    proof["diagnostic_rejected_by_default"] = reject("diagnostic-default",
        fixture("two_cycles_clear"), "original attempt diagnostic provenance differs", False)
    changed = altered("changed-source")
    path = changed / "original-events.json"
    path.write_text(path.read_text() + " ")
    proof["changed_source"] = reject("changed-source", changed, "source hash mismatch")
    shortened = altered("shortened")
    path = shortened / "saved-manifest.json"
    packet = json.loads(path.read_text())
    packet["duration_frames"] = 600
    path.write_text(json.dumps(packet) + "\n")
    proof["shortened_original"] = reject("shortened", shortened,
        "exact 45 second history missing")
    changed_join = altered("changed-frame-join")
    event_path = changed_join / "original-events.json"
    events = json.loads(event_path.read_text())
    events[450]["time_s"] += 0.01
    event_path.write_text(json.dumps(events) + "\n")
    saved_path = changed_join / "saved-manifest.json"
    saved = json.loads(saved_path.read_text())
    saved["sources"]["original_events"]["sha256"] = sha(event_path)
    saved_path.write_text(json.dumps(saved) + "\n")
    proof["changed_middle_frame_join"] = reject("changed-frame-join", changed_join,
        "Sealed original event/trace/video frame join differs at 450")
    fixed = altered("changed-fixed-route")
    route_path = fixed / "route_ref.json"
    route = json.loads(route_path.read_text())
    route["comparison_probe_change"] = "separate reviewed route"
    route_path.write_text(json.dumps(route) + "\n")
    site_path = fixed / "native-site.json"
    site = json.loads(site_path.read_text())
    site["original_sources"]["route_ref"]["sha256"] = sha(route_path)
    site_path.write_text(json.dumps(site) + "\n")
    saved_path = fixed / "saved-manifest.json"
    saved = json.loads(saved_path.read_text())
    saved["sources"]["route"]["sha256"] = sha(route_path)
    saved_path.write_text(json.dumps(saved) + "\n")
    proof["changed_rehashed_fixed_route"] = reject("changed-fixed-route", fixed,
        "fixed condition differs: route_sha256")
    output = HERE / "cpu-original-comparison-proofs.json"
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"positive_comparisons": len(PAIRS), "negative_checks": 5,
                      "passed": True}))


if __name__ == "__main__":
    main()
