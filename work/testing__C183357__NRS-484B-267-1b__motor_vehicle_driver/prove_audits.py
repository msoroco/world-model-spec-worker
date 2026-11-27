"""Run independent source-bound delivery and comparison CPU audits."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from native_packet import AID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c183357-1b/audits-v1"
MANIFEST = HERE / "execution-manifest.json"
PLAN = HERE / "case-plan.json"
HISTORY = "original-curb-position-history.jsonl"
CHECKS = ["native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(command):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
        SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / ".runtime-work/c183357-1b/output-root"),
        TMPDIR=str(ROOT / ".runtime-work/c183357-1b/tmp"))
    return subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)


def log(name, done):
    path = HERE / name
    path.write_text((done.stdout + done.stderr).rstrip() + "\n", encoding="utf-8")
    return path


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        name = case_id.removeprefix(AID + "__")
        attempt = ROOT / ".runtime-work/c183357-1b" / ("compat-" + name + "-v4")
        output = SCRATCH / (name + "-delivery.json")
        if output.exists():
            output.unlink()
        command = [sys.executable, str(HERE / "delivery_audit.py"),
                   "--case-id", case_id, "--attempt", str(attempt),
                   "--plan", str(PLAN), "--output", str(output)]
        done = run(command)
        positive = log("cpu-delivery-" + name + ".log", done)
        if done.returncode or len(json.loads(output.read_text()).get("four_view_full_decode", {})) != 4:
            raise RuntimeError("independent curb delivery failed: " + positive.read_text()[-900:])
        missing = SCRATCH / (name + "-missing")
        if missing.exists():
            shutil.rmtree(missing)
        shutil.copytree(attempt, missing, copy_function=os.link)
        (missing / HISTORY).unlink()
        negative_output = SCRATCH / (name + "-negative.json")
        if negative_output.exists():
            negative_output.unlink()
        negative = command.copy()
        negative[negative.index("--attempt") + 1] = str(missing)
        negative[negative.index("--output") + 1] = str(negative_output)
        failed = run(negative)
        negative_log = log("cpu-delivery-" + name + "-negative.log", failed)
        expected = "Missing required source: " + HISTORY
        if failed.returncode == 0 or expected not in negative_log.read_text():
            raise RuntimeError("missing-source delivery negative failed: " + name)
        entry["delivery_acceptance"] = {
            "case_id": case_id, "sets": ["full-test"], "checks": CHECKS,
            "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
            "command": " ".join(command), "test_exit_code": 0,
            "test_log": positive.name, "test_log_sha256": sha(positive),
            "negative_command": " ".join(negative), "negative_exit_code": failed.returncode,
            "negative_expected_error": expected, "negative_log": negative_log.name,
            "negative_log_sha256": sha(negative_log),
            "diagnostic_fixture": True, "physical_acceptance_claimed": False}
        print("independent delivery", name, "passed", flush=True)
    write(MANIFEST, manifest)
    plan = json.loads(PLAN.read_text())
    receipts = []
    for comparison in plan["comparisons"]:
        name = comparison["comparison_id"]
        command = [sys.executable, str(HERE / "comparison_audit.py"),
                   "--comparison-id", AID + "__" + name, "--plan", str(PLAN)]
        for case_id in comparison["case_ids"]:
            suffix = case_id.removeprefix(AID + "__")
            command += ["--attempt", str(ROOT / ".runtime-work/c183357-1b" /
                                         ("compat-" + suffix + "-v4"))]
        output = SCRATCH / (name + "-comparison.json")
        if output.exists():
            output.unlink()
        command += ["--output", str(output)]
        done = run(command)
        proof_log = log("cpu-comparison-" + name + ".log", done)
        if done.returncode:
            raise RuntimeError("independent curb comparison failed: " + proof_log.read_text()[-900:])
        receipts.append({"comparison_id": name, "case_ids": comparison["case_ids"],
            "audit": {"script": "comparison_audit.py",
                      "script_sha256": sha(HERE / "comparison_audit.py"),
                      "command": " ".join(command), "test_exit_code": 0,
                      "test_log": proof_log.name, "test_log_sha256": sha(proof_log),
                      "result_sha256": sha(output), "diagnostic_fixture": True,
                      "physical_acceptance_claimed": False}})
        print("independent comparison", name, "passed", flush=True)
    first = plan["comparisons"][0]
    base = ROOT / ".runtime-work/c183357-1b" / (
        "compat-" + first["case_ids"][0].removeprefix(AID + "__") + "-v4")
    contrast = ROOT / ".runtime-work/c183357-1b" / (
        "compat-" + first["case_ids"][1].removeprefix(AID + "__") + "-v4")
    small = SCRATCH / "comparison-negative-source"
    small.mkdir(exist_ok=True)
    for name in ("config.json", "diagnostic-source-note.json", "curb-site.json",
                 "camera-frame-map.jsonl", "video_frames.jsonl", "trace.jsonl", HISTORY):
        shutil.copyfile(contrast / name, small / name)
    negative_protocol = []
    for kind, expected in (("missing", "Missing required source: " + HISTORY),
                           ("fixed", "curb comparison fixed site context differs")):
        target = small / HISTORY
        if kind == "missing":
            target.unlink()
        else:
            shutil.copyfile(contrast / HISTORY, target)
            site = json.loads((small / "curb-site.json").read_text())
            site["route_source"] = "deliberately-different-fixed-context"
            write(small / "curb-site.json", site)
        command = [sys.executable, str(HERE / "comparison_audit.py"),
                   "--comparison-id", AID + "__" + first["comparison_id"],
                   "--plan", str(PLAN), "--attempt", str(base),
                   "--attempt", str(small), "--output", str(SCRATCH / ("rejected-" + kind + ".json"))]
        rejected = SCRATCH / ("rejected-" + kind + ".json")
        if rejected.exists():
            rejected.unlink()
        done = run(command)
        proof_log = log("cpu-comparison-negative-" + kind + ".log", done)
        if done.returncode == 0 or expected not in proof_log.read_text():
            raise RuntimeError("comparison negative protocol failed: " + kind)
        negative_protocol.append({"kind": kind, "command": " ".join(command),
                                  "exit_code": done.returncode, "expected_error": expected,
                                  "log": proof_log.name, "log_sha256": sha(proof_log)})
    write(HERE / "comparison-audits.json", {
        "format": "worker-comparison-audits", "assignment_id": AID,
        "comparisons": receipts, "negative_protocol": negative_protocol})


if __name__ == "__main__":
    main()
