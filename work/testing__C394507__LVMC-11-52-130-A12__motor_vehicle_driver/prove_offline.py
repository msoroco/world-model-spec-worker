"""Run every exact primary and camera-fallback CPU construction proof."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(text):
    return "\n".join(line.rstrip() for line in text.splitlines()).rstrip() + "\n"


def main():
    scratch = REPO / ".runtime-work" / "c394507-nov26"
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(scratch)
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(scratch)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        tag = entry["case_id"].rsplit("__", 1)[-1]
        for candidate in ("primary", "fallback1"):
            selected = entry if candidate == "primary" else entry["candidates"][0]
            command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                       "offline", "--manifest", str(MANIFEST),
                       "--case", entry["case_id"], "--candidate", candidate,
                       "--output", "{fresh output under .runtime-work}",
                       "--python", str(REPO / ".venv-cpu/bin/python")]
            with tempfile.TemporaryDirectory(prefix="crosswalk-offline-", dir=scratch) as temporary:
                output = Path(temporary) / "bundle"
                run = [str(output) if part == "{fresh output under .runtime-work}" else part
                       for part in command]
                completed = subprocess.run(run, cwd=REPO, env=os.environ,
                                           text=True, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, timeout=300)
                if completed.returncode:
                    raise RuntimeError(tag + " " + candidate + " offline failed: " +
                                       completed.stdout[-1200:])
                log_path = HERE / f"proof-offline-{tag}-{candidate}.log"
                log_path.write_text(clean((output / "offline.log").read_text()))
            selected["offline"] = {
                "construction_sha256": selected["construction_sha256"],
                "command": " ".join(command), "exit_code": 0,
                "log": log_path.name, "log_sha256": sha(log_path)}
            print(tag, candidate, "passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
