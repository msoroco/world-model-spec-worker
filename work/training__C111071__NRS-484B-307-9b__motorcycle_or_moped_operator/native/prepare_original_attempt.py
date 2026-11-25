"""Prepare an original Native attempt for recorded-only saved processing.

A named review must be supplied after capture. This step does not judge the
physical or legal outcome; the independent delivery audit remains separate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from source_bridge import convert


def prepare(attempt: Path, review: Path, diagnostic: bool = False):
    attempt = Path(attempt)
    manifest_path = attempt / "capture" / "manifest.json"
    if not diagnostic:
        if not manifest_path.is_file():
            raise ValueError("Original Native capture manifest absent")
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("source_kind") != "original_native":
            raise ValueError("Original Native capture required before source review")
    result = convert(attempt, Path(review))
    return {"prepared_for_saved_processing": True,
            "diagnostic_only": diagnostic, **result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--review", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.attempt, args.review), sort_keys=True))


if __name__ == "__main__":
    main()
