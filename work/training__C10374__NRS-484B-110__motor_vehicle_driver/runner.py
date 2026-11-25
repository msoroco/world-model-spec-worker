"""Dispatch one exact C10374 case through the pinned prospective runtime."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--output", required=True)
    parser.add_argument("--python", default=os.environ.get("CARLA_PYTHON"))
    parser.add_argument("--host", default=os.environ.get("CARLA_HOST", "localhost"))
    parser.add_argument("--port", default=os.environ.get("CARLA_PORT", "2000"))
    args = parser.parse_args()
    if not args.python:
        raise ValueError("Supply original CARLA Python")
    command = [sys.executable, str(ROOT / "runtime.py"), "capture", "--manifest",
               str(HERE / "execution-manifest.json"), "--case", args.case,
               "--candidate", args.candidate, "--output", args.output,
               "--python", args.python, "--host", args.host, "--port", str(args.port)]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
