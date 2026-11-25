"""Reproduce four red-X independent acceptance protocol positives and negatives."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUFFIXES = ("adjacent_travel", "lateral_entry", "red_lane_stand", "red_lane_drive")


def main() -> None:
    script = ROOT / "independent/prove_delivery_audit.py"
    for suffix in SUFFIXES:
        case_id = ROOT.name + "__" + suffix
        command = [sys.executable, str(script), case_id]
        positive = subprocess.run(command, capture_output=True, text=True, check=False)
        negative = subprocess.run(command + ["--negative"], capture_output=True,
                                  text=True, check=False)
        if (positive.returncode != 0 or
                "diagnostic protocol positive and five negatives passed" not in positive.stdout or
                negative.returncode != 1 or
                "original pixel review missing or stale" not in negative.stderr):
            raise AssertionError("independent exact acceptance proof failed: " + case_id)
        print(case_id + ": positive and stale-review negative passed", flush=True)


if __name__ == "__main__":
    main()
