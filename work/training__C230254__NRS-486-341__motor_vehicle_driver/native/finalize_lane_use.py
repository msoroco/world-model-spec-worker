"""Saved-only source-shaped lane geometry finalizer (no legal verdict)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lane_use import measure_joined_frames


def finalize(source: Path, output: Path):
    if not source.is_file():
        raise ValueError("Native geometry source file is missing")
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    measured = measure_joined_frames(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in measured))
    return len(measured)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"measured_frames": finalize(args.source, args.output)}))


if __name__ == "__main__":
    main()
