"""Prove exact rail delivery audits on saved diagnostic originals and missing source."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parents[1]
MANIFEST = WORK / "execution-manifest.json"
AUDITOR = WORK / "delivery_audit.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    data = json.loads(MANIFEST.read_text())
    sets = json.loads((ROOT / "inputs" / WORK.name / "assignment.json").read_text())["selection_targets"]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(ROOT / ".runtime-work"))
    scratch = ROOT / ".runtime-work" / ("c202465-lvmc-delivery-audit-" + str(time.time_ns()))
    scratch.mkdir(parents=True)
    for entry in data["cases"]:
        case = entry["case_id"]
        suffix = case.split("__")[-1]
        saved = entry["saved_proof"]
        base = [sys.executable, "-B", str(AUDITOR), "--case", case,
                "--candidate", "primary", "--attempt", saved["attempt"],
                "--processing", saved["processing"], "--diagnostic"]
        positive = base + ["--output", str(scratch / (suffix + "-positive.json"))]
        negative = base + ["--output", str(scratch / (suffix + "-negative.json")),
                           "--omit-source", "rail-rays.jsonl"]
        folder = WORK / "delivery-proofs" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        passed = subprocess.run(positive, cwd=ROOT, env=env, capture_output=True, text=True)
        pass_log = folder / "positive.log"
        pass_log.write_text((passed.stdout + passed.stderr).rstrip() + "\n")
        if passed.returncode:
            raise RuntimeError("Delivery positive failed " + suffix + ": " + pass_log.read_text()[-2000:])
        failed = subprocess.run(negative, cwd=ROOT, env=env, capture_output=True, text=True)
        fail_log = folder / "negative.log"
        fail_log.write_text((failed.stdout + failed.stderr).rstrip() + "\n")
        if failed.returncode == 0 or "Missing source: rail-rays.jsonl" not in fail_log.read_text():
            raise RuntimeError("Delivery negative failed to reject " + suffix)
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": sets,
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion",
                       "two_direction_rail_sight_and_exception_source_review"],
            "script": str(AUDITOR.relative_to(WORK)), "script_sha256": sha(AUDITOR),
            "command": " ".join(positive), "test_exit_code": 0,
            "test_log": str(pass_log.relative_to(WORK)), "test_log_sha256": sha(pass_log),
            "negative_command": " ".join(negative),
            "negative_exit_code": failed.returncode,
            "negative_expected_error": "Missing source: rail-rays.jsonl",
            "negative_log": str(fail_log.relative_to(WORK)),
            "negative_log_sha256": sha(fail_log),
        }
        MANIFEST.write_text(json.dumps(data, indent=2) + "\n")
        print("PASS delivery audit", suffix, flush=True)


if __name__ == "__main__":
    main()
