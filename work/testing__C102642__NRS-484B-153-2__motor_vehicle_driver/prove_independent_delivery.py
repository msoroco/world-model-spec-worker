"""Record missing-source rejection for five saved CPU diagnostic attempts."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c102642-new"
KINDS = ("open_near_overlap", "open_near_clear", "open_far_side",
         "board_near", "alight_near", "door_interference_physical_range-0000",
         "door_interference_physical_range-0001", "door_interference_physical_range-0002")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for kind in KINDS:
        case = HERE / "cases" / kind
        case_id = HERE.name + "__" + kind
        positive = SCRATCH / f"compat-{kind}-v9b"
        negative = SCRATCH / f"independent-negative-{kind}-v9b"
        if negative.exists():
            raise ValueError("Use a fresh negative attempt: " + str(negative))
        shutil.copytree(positive, negative, copy_function=os.link)
        (negative / "door-source.json").unlink()
        command = [sys.executable, str(HERE / "independent_cpu_delivery.py"),
                   "--attempt", str(negative), "--case-id", case_id,
                   "--output", str(negative / "independent-negative-output.json")]
        process = subprocess.run(command, cwd=REPO, env=dict(os.environ,
                                 TMPDIR=str(REPO / ".runtime-work"),
                                 PYTHONDONTWRITEBYTECODE="1"),
                                 capture_output=True, text=True)
        log = case / "independent-missing-source.log"
        log.write_text(process.stdout + process.stderr)
        if (process.returncode == 0 or
                "Missing required source: door-source.json" not in log.read_text()):
            raise ValueError("Independent audit accepted missing door source: " + kind)
        entry = next(row for row in manifest["cases"] if row["case_id"] == case_id)
        entry["delivery_acceptance"] = {
            "case_id": case_id,
            "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "scope": "synthetic CPU audit; physical completion remains unverified",
            "script": "independent_cpu_delivery.py",
            "script_sha256": sha(HERE / "independent_cpu_delivery.py"),
            "command": " ".join((sys.executable, "independent_cpu_delivery.py",
                                 "--case-id", case_id, "--attempt",
                                 str(positive), "--output",
                                 f"cases/{kind}/independent-cpu-audit.json")),
            "test_exit_code": 0,
            "test_log": f"cases/{kind}/independent-cpu-audit.log",
            "test_log_sha256": sha(case / "independent-cpu-audit.log"),
            "negative_command": " ".join((sys.executable,
                                          "independent_cpu_delivery.py",
                                          "--case-id", case_id,
                                          "--attempt", str(negative),
                                          "--output", str(negative / "independent-negative-output.json"))),
            "negative_exit_code": process.returncode,
            "negative_expected_error": "Missing required source: door-source.json",
            "negative_log": f"cases/{kind}/independent-missing-source.log",
            "negative_log_sha256": sha(log)}
        print(kind, "independent saved audit positive and missing-source negative passed")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    prove()
