"""Reprove the selected synthetic CPU chains on the pinned active runtime."""

import concurrent.futures
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PKG = Path(__file__).resolve().parent
SCRATCH = ROOT / ".runtime-work" / "owner129-current"
VALIDATOR = ROOT / ".runtime-work/owner199/decoder-current/.lake/build/bin/adapterCheck"
ASSIGNMENT = PKG.name
DISTANCES = (90, 100, 110, 290, 300, 310)
CANDIDATES = ("primary", "fallback1", "fallback2")


def prove(item):
    distance, candidate = item
    tag = f"{distance}-{candidate}"
    manifest = (PKG / f"current-selected-{distance}-fallback1-proof-manifest.json"
                if candidate == "fallback1" else PKG / "execution-manifest.json")
    case_id = f"{ASSIGNMENT}__{distance}"
    attempt = SCRATCH / f"active-{tag}-compat"
    saved = SCRATCH / f"active-{tag}-saved"
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(ROOT / ".runtime-work"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / f"env-{tag}"),
               MPLCONFIGDIR=str(SCRATCH / "mpl"))
    common = ["--manifest", str(manifest), "--case", case_id,
              "--library", str(ROOT / "runtime/library"), "--validator", str(VALIDATOR)]
    command = [str(ROOT / ".venv-cpu/bin/python"), str(ROOT / "runtime.py"),
               "compatibility", *common, "--candidate", candidate, "--output", str(attempt)]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
    if completed.returncode:
        (PKG / f"current-active-{tag}-error.log").write_bytes(
            completed.stdout[-100000:] + completed.stderr[-100000:])
        return tag, "compatibility failed"
    receipt = json.loads(completed.stdout)
    if not receipt.get("passed"):
        return tag, "compatibility returned false"
    (PKG / f"current-active-{tag}-receipt.json").write_bytes(completed.stdout)
    shutil.copyfile(attempt / "compatibility-analysis.log",
                    PKG / f"current-active-{tag}-analysis.log")
    shutil.copyfile(attempt / "negative-analysis.log",
                    PKG / f"current-active-{tag}-negative.log")
    command = [str(ROOT / ".venv-cpu/bin/python"), str(ROOT / "runtime.py"),
               "process-saved", *common, "--attempt", str(attempt), "--output", str(saved)]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
    if completed.returncode:
        (PKG / f"current-active-{tag}-saved-error.log").write_bytes(
            completed.stdout[-100000:] + completed.stderr[-100000:])
        return tag, "saved processing failed"
    receipt = json.loads(completed.stdout)
    if not receipt.get("passed") or not receipt.get("recorded_only"):
        return tag, "saved processing returned false"
    (PKG / f"current-active-{tag}-saved-receipt.json").write_bytes(completed.stdout)
    return tag, "passed"


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for tag, status in pool.map(prove, ((d, c) for d in DISTANCES for c in CANDIDATES)):
            print(tag, status, flush=True)


if __name__ == "__main__":
    main()
