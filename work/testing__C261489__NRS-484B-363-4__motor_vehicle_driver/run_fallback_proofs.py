"""Run exact fallback1 offline and positive/negative compatibility proofs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c261489-owner-nov27b"
MANIFEST = HERE / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(source: Path, destination: Path) -> None:
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    destination.write_text("\n".join(lines) + "\n")


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    env = os.environ.copy()
    env.update(TMPDIR=str(SCRATCH), SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               PYTHONDONTWRITEBYTECODE="1")
    for entry in manifest["cases"]:
        case = entry["case_id"]
        name = case[len(HERE.name) + 2:]
        fallback = entry["candidates"][0]
        dest = SCRATCH / ("fallback-offline-" + name + "-v2")
        command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                   "offline", "--manifest", str(MANIFEST), "--case", case,
                   "--output", str(dest), "--python", str(REPO / ".venv-cpu/bin/python"),
                   "--candidate", "fallback1"]
        if dest.exists():
            raise ValueError("Fresh fallback offline destination required: " + name)
        completed = subprocess.run(command, cwd=REPO, env=env, text=True,
                                   capture_output=True, timeout=300)
        if completed.returncode:
            raise RuntimeError(name + " fallback offline: " + completed.stderr[-1800:])
        log = HERE / ("cpu-fallback-offline-" + name + ".log")
        clean(dest / "offline.log", log)
        if "OK" not in log.read_text():
            raise ValueError("fallback offline lacked passing tests: " + name)
        fallback["offline"] = {
            "command": " ".join(command), "exit_code": 0,
            "construction_sha256": fallback["construction_sha256"],
            "log": log.name, "log_sha256": sha(log),
        }
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(name, "fallback offline passed", flush=True)
    for entry in manifest["cases"]:
        case = entry["case_id"]
        name = case[len(HERE.name) + 2:]
        fallback = entry["candidates"][0]
        dest = SCRATCH / ("fallback-compat-" + name + "-v2")
        command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                   "compatibility", "--manifest", str(MANIFEST), "--case", case,
                   "--output", str(dest), "--library", str(REPO / "runtime/library"),
                   "--validator", str(VALIDATOR), "--candidate", "fallback1"]
        if dest.exists():
            raise ValueError("Fresh fallback compatibility destination required: " + name)
        completed = subprocess.run(command, cwd=REPO, env=env, text=True,
                                   capture_output=True, timeout=600)
        if completed.returncode:
            raise RuntimeError(name + " fallback compatibility: " + completed.stderr[-1800:])
        receipt = json.loads((dest / "compatibility.json").read_text())
        if receipt.get("passed") is not True or receipt.get("candidate_id") != "fallback1":
            raise ValueError("fallback compatibility selected another candidate: " + name)
        positive = HERE / ("cpu-fallback-compat-" + name + ".log")
        negative = HERE / ("cpu-fallback-compat-" + name + "-negative.log")
        clean(dest / "compatibility-analysis.log", positive)
        clean(dest / "negative-analysis.log", negative)
        if receipt["log_sha256"] != sha(positive) or receipt["negative_log_sha256"] != sha(negative):
            raise ValueError("fallback compatibility logs changed: " + name)
        receipt_path = HERE / ("cpu-fallback-compat-" + name + "-receipt.json")
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        fallback["compatibility"] = {
            "command": " ".join(command), "receipt": receipt_path.name,
            "sha256": sha(receipt_path), "log": positive.name,
            "negative_log": negative.name,
        }
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(name, "fallback positive/negative compatibility passed", flush=True)


if __name__ == "__main__":
    main()
