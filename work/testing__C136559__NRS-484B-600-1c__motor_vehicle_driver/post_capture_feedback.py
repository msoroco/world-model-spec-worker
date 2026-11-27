"""Print the latest actionable recorded-only feedback from saved processing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    versions = sorted(p for p in args.output.glob("v[0-9][0-9][0-9][0-9]") if p.is_dir())
    if not versions:
        raise ValueError("saved processing produced no output version")
    feedback = versions[-1] / "feedback.json"
    if not feedback.is_file():
        raise ValueError("latest saved processing has no feedback.json")
    value = json.loads(feedback.read_text())
    if value.get("recorded_only") is not True or value.get("native_replay_requested") is not False:
        raise ValueError("saved feedback violates recorded-only contract")
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
