"""Dispatch one exact C104496 case through the pinned prospective runtime."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--candidate", default="primary")
    p.add_argument("--output", required=True)
    p.add_argument("--python", default=os.environ.get("CARLA_PYTHON"))
    p.add_argument("--host", default=os.environ.get("CARLA_HOST", "localhost"))
    p.add_argument("--port", default=os.environ.get("CARLA_PORT", "2000"))
    args = p.parse_args()
    if not args.python:
        raise ValueError("Supply original CARLA Python")
    command = [sys.executable, str(ROOT / "runtime.py"), "capture", "--manifest", str(HERE / "execution-manifest.json"), "--case", args.case, "--candidate", args.candidate, "--output", args.output, "--python", args.python, "--host", args.host, "--port", str(args.port)]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
