"""Dispatch one exact source-gated Native bundle from the selected manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def check(case_id=None):
    config = json.loads((HERE / "config.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    selected = {row["case_id"]: row for row in manifest["cases"]}
    if set(selected) != set(config["supported_case_ids"]):
        raise ValueError("Root dispatch and selected exact cases differ")
    if case_id is not None and case_id not in selected:
        raise ValueError("Unknown exact case")
    for row in selected.values():
        source = HERE / row["construction"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != row["construction_sha256"]:
            raise ValueError("Selected exact construction changed: " + row["case_id"])
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default=os.environ.get("CARLA_HOST", "localhost"))
    parser.add_argument("--port", default=os.environ.get("CARLA_PORT", "2000"))
    parser.add_argument("--python", default=os.environ.get("CARLA_PYTHON"))
    args = parser.parse_args()
    check(args.case)
    if args.check:
        print("four exact selected Native bundles verified")
        return
    if not args.case or not args.output_dir or not args.python:
        raise ValueError("Exact case, fresh output and Native Python are required")
    subprocess.run([sys.executable, str(REPO / "runtime.py"), "capture", "--manifest",
                    str(HERE / "execution-manifest.json"), "--case", args.case,
                    "--output", args.output_dir, "--host", args.host,
                    "--port", str(args.port), "--python", args.python],
                   cwd=REPO, check=True)


if __name__ == "__main__":
    main()
