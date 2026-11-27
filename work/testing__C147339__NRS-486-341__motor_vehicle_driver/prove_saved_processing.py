"""Exercise recorded-only process-saved for every selected diagnostic case."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c147339-saved-processing"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"
SKIP = {"result.json", "analysis-report.json", "channels", "traffic_spec", "converted",
        "compatibility.json", "processing.json", "feedback.json", "candidate-selection.json"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def source_for(suffix):
    if suffix == "motorcycle_adjacent_clear":
        return REPO / ".runtime-work/c147339-compat-third"
    return REPO / (".runtime-work/c147339-compat-batch-" + suffix + "-primary")


def one(entry):
    case = entry["case_id"]
    suffix = case.split("__")[-1]
    attempt, output = SCRATCH / (suffix + "-source"), SCRATCH / (suffix + "-processed")
    if attempt.exists() or output.exists():
        raise ValueError("Retain prior saved proof: " + suffix)
    attempt.mkdir()
    for source in source_for(suffix).iterdir():
        if source.name in SKIP or source.name.startswith(("source-", "final-decode", "primary", "annotated")):
            continue
        target = attempt / source.name
        if source.is_dir():
            shutil.copytree(source, target, copy_function=os.link)
        else:
            os.link(source, target)
    command = [sys.executable, str(REPO / "runtime.py"), "process-saved",
               "--manifest", str(ROOT / "execution-manifest.json"), "--case", case,
               "--attempt", str(attempt), "--output", str(output),
               "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "pipeline"))
    log = ROOT / ("cpu-post-capture-" + suffix + ".log")
    completed = subprocess.run(command, cwd=REPO, env=environment, capture_output=True, text=True)
    text = (completed.stdout + completed.stderr).rstrip() + "\n"
    log.write_text(text)
    if completed.returncode:
        raise ValueError("process-saved failed: " + suffix + ": " + text[-1500:])
    receipt = json.loads((output / "v0001/processing.json").read_text())
    if not receipt.get("passed") or not receipt.get("recorded_only") or not receipt.get("originals_preserved"):
        raise ValueError("Recorded-only receipt missing: " + suffix)
    return suffix, case, command, log, sha(log)


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, entry) for entry in manifest["cases"]]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    for suffix, case, command, log, log_hash in results:
        entry = next(item for item in manifest["cases"] if item["case_id"] == case)
        entry["post_capture"] = {
            "command": " ".join(command),
            "feedback_command": " ".join(command).replace("-processed", "-feedback"),
            "recorded_only": True, "test_exit_code": 0,
            "test_log": log.name, "test_log_sha256": log_hash,
            "scope": "CPU diagnostic saved-only processing after separate ownership closure proof"}
        print(suffix, "saved-only passed", flush=True)
    write(manifest_path, manifest)


if __name__ == "__main__":
    main()
