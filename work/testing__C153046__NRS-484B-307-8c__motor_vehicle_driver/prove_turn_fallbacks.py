"""Run pinned exact offline and positive/negative compatibility for fallbacks."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], log: Path) -> None:
    with log.open("w") as stream:
        process = subprocess.run(command, cwd=REPO, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                 stdout=stream, stderr=subprocess.STDOUT, timeout=900)
    if process.returncode:
        raise ValueError("pinned fallback proof failed: " + str(log))


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        candidate = entry["candidates"][0]
        folder = ROOT / "diagnostics" / suffix
        offline_dir = REPO / ".runtime-work" / ("c153046-fallback-offline-" + run_id) / suffix
        command = [sys.executable, str(REPO / "runtime.py"), "offline", "--manifest", str(MANIFEST),
                   "--case", case_id, "--candidate", "fallback1", "--output", str(offline_dir)]
        run(command, folder / "fallback-offline-command.log")
        offline_log = folder / "fallback-offline.log"
        shutil.copyfile(offline_dir / "offline.log", offline_log)
        candidate["offline"] = {"command": " ".join(command), "exit_code": 0,
                                "construction_sha256": candidate["construction_sha256"],
                                "log": str(offline_log.relative_to(ROOT)), "log_sha256": sha(offline_log)}
        compat_dir = REPO / ".runtime-work" / ("c153046-fallback-compat-" + run_id) / suffix
        command = [sys.executable, str(REPO / "runtime.py"), "compatibility", "--manifest", str(MANIFEST),
                   "--case", case_id, "--candidate", "fallback1", "--output", str(compat_dir),
                   "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
        run(command, folder / "fallback-compat-command.log")
        receipt = folder / "fallback-compat.json"
        analysis = folder / "fallback-compat-analysis.log"
        negative = folder / "fallback-negative-analysis.log"
        shutil.copyfile(compat_dir / "compatibility.json", receipt)
        shutil.copyfile(compat_dir / "compatibility-analysis.log", analysis)
        shutil.copyfile(compat_dir / "negative-analysis.log", negative)
        value = json.loads(receipt.read_text())
        if (value.get("passed") is not True or value.get("candidate_id") != "fallback1" or
                value.get("construction_sha256") != candidate["construction_sha256"]):
            raise ValueError("fallback compatibility identity differs: " + suffix)
        candidate["compatibility"] = {"receipt": str(receipt.relative_to(ROOT)), "sha256": sha(receipt),
                                      "log": str(analysis.relative_to(ROOT)),
                                      "negative_log": str(negative.relative_to(ROOT))}
        candidate["proof_status"] = "synthetic_cpu_offline_and_positive_negative_compatibility_passed"
        print("pinned fallback offline and compatibility passed", suffix, flush=True)
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
