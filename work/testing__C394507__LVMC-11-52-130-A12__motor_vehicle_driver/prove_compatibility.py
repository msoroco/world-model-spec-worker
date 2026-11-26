"""Bind fresh primary and camera fallback compatibility receipts to this manifest."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
PYTHON = str(REPO / ".venv-cpu/bin/python")
SCRATCH = REPO / ".runtime-work/c394507-nov26"
VALIDATOR = REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(path):
    body = Path(path).read_text().rstrip()
    return body + "\n" if body else ""


def main():
    os.environ["TMPDIR"] = os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        tag = entry["case_id"].rsplit("__", 1)[-1]
        for candidate in ("primary", "fallback1"):
            selected = entry if candidate == "primary" else entry["candidates"][0]
            output = SCRATCH / ("compat-" + tag + "-" + candidate +
                                "-" + str(time.time_ns()))
            command = [PYTHON, str(REPO / "runtime.py"), "compatibility",
                       "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--candidate", candidate, "--output", str(output),
                       "--library", str(REPO / "runtime/library"),
                       "--validator", str(VALIDATOR)]
            run = subprocess.run(command, cwd=REPO, env=os.environ, capture_output=True,
                                 text=True, timeout=600)
            if run.returncode:
                raise RuntimeError(tag + " " + candidate + ": " +
                                   (run.stdout + run.stderr)[-2500:])
            prefix = "proof-compat-" + tag + "-" + candidate
            log = HERE / (prefix + ".log")
            negative = HERE / (prefix + "-negative.log")
            receipt = HERE / (prefix + "-receipt.json")
            log.write_text(clean(output / "compatibility-analysis.log"))
            negative.write_text(clean(output / "negative-analysis.log"))
            shutil.copyfile(output / "compatibility.json", receipt)
            selected["compatibility"] = {
                "command": " ".join(command), "log": log.name,
                "negative_log": negative.name, "receipt": receipt.name,
                "sha256": sha(receipt), "negative_log_sha256": sha(negative)}
            if candidate == "primary":
                entry["negative"] = {"log": negative.name,
                                     "log_sha256": sha(negative)}
            MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
            print(tag, candidate, "compatibility passed", flush=True)


if __name__ == "__main__":
    main()
