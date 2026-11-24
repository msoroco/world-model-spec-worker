"""Strip derived outputs from one synthetic compatibility attempt for replay.

The staged copy lives under .runtime-work and preserves all original acquisition
bytes. A primary fixture omits its stale manifest-bound candidate selection.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil


DERIVED = (
    "signal_head_history.jsonl", "ego_body_history.jsonl",
    "vehicle_body_history.jsonl", "pedestrian_body_history.jsonl",
    "intersection_geometry.jsonl", "crosswalk_geometry.jsonl",
    "lawful_presence_context.jsonl", "original_lamp_pixels.jsonl",
    "site-source-survey.json", "candidate-selection.json",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    source = Path(args.source).resolve()
    target = Path(args.target).resolve()
    scratch = Path.cwd() / ".runtime-work"
    if not source.is_dir() or not target.is_relative_to(scratch.resolve()) or target.exists():
        raise ValueError("saved fixture must be new and under .runtime-work")
    shutil.copytree(source, target, copy_function=os.link)
    for name in DERIVED:
        (target / name).unlink(missing_ok=True)
    print("staged saved-only diagnostic fixture: " + str(target))


if __name__ == "__main__":
    main()
