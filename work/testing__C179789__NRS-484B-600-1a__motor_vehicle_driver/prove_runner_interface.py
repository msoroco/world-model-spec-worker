"""Prove the pinned capture CLI rejects a missing reviewed site packet."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main() -> None:
    bundles = sorted((ROOT / ".runtime-work/c179789-offline-proof-v4").glob(
        "offline-reference-*/bundle/runner.py"))
    if len(bundles) != 1:
        raise ValueError("expected one rebuilt reference bundle")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join((
        str(ROOT / "runtime/scenario_pipeline"), str(ROOT / "runtime/python")))
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable, str(bundles[0]), "--output-dir",
               str(ROOT / ".runtime-work/c179789-runner-cli-negative"),
               "--host", "127.0.0.1", "--port", "2000"]
    result = subprocess.run(command, capture_output=True, text=True, env=environment)
    if (result.returncode != 2 or
            "reviewed native-site-packet.json is required" not in result.stderr or
            "unrecognized arguments" in result.stderr):
        raise ValueError("capture CLI did not reject absent reviewed source correctly: "
                         + result.stderr)
    print("Pinned --output-dir interface parsed; absent reviewed Native site packet rejected before CARLA import")


if __name__ == "__main__":
    main()
