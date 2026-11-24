"""Bind per-case independent audit protocol and strict diagnostic rejection."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ERROR = "diagnostic fixture cannot pass delivery acceptance"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    script = ROOT / "independent/delivery_audit.py"
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        folder = ROOT / "diagnostics" / suffix
        base = [sys.executable, str(ROOT / "prove_delivery_case.py"), "--case", case_id]
        positive_log = folder / "delivery-protocol.log"
        negative_log = folder / "delivery-rejection.log"
        with positive_log.open("w") as stream:
            positive = subprocess.run(base, cwd=REPO, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                      stdout=stream, stderr=subprocess.STDOUT, timeout=60)
        with negative_log.open("w") as stream:
            negative = subprocess.run(base + ["--strict"], cwd=REPO,
                                      env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                      stdout=stream, stderr=subprocess.STDOUT, timeout=60)
        if positive.returncode or not negative.returncode or ERROR not in negative_log.read_text():
            raise ValueError("independent diagnostic protocol/rejection failed: " + suffix)
        entry["delivery_acceptance"] = {
            "case_id": case_id, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion",
                       "observation_replay"],
            "script": str(script.relative_to(ROOT)), "script_sha256": sha(script),
            "command": shlex.join(base), "test_exit_code": 0,
            "test_log": str(positive_log.relative_to(ROOT)), "test_log_sha256": sha(positive_log),
            "negative_command": shlex.join(base + ["--strict"]),
            "negative_exit_code": negative.returncode, "negative_expected_error": ERROR,
            "negative_log": str(negative_log.relative_to(ROOT)), "negative_log_sha256": sha(negative_log),
            "scope": "synthetic CPU protocol only; original pixel and physical audit remains pending",
        }
        print("independent delivery protocol and strict rejection passed", suffix, flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
