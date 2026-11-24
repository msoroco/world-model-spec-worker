"""Stage source-only diagnostic acquisition for pinned process-saved replay.

Compatibility writes derived analysis into its attempt. The saved processor
requires a clean acquisition attempt so that it can rebuild those products.
This helper retains sealed source files and the original graph directory while
excluding compatibility, analysis, rendering, and converter outputs.
"""

import argparse
import shutil
from pathlib import Path


DERIVED_FILES = {
    "analysis-report.json", "compatibility-analysis.log", "compatibility.json",
    "event_review.json", "event_review.webm", "event_review_encoder.log",
    "event_review_frames.jsonl", "final-decode.json", "negative-analysis.log",
    "result.json", "review_label.txt", "review_measured_speed.ass",
    "review_render.lock", "trace.jsonl", "video_frames.jsonl",
}
DERIVED_DIRS = {"channels", "converted", "traffic_spec", "tests"}


def stage(source: Path, output: Path) -> None:
    source = source.resolve(strict=True)
    output = output.resolve()
    if ".runtime-work" not in output.parts:
        raise ValueError("output must be scratch under .runtime-work")
    if source == output or source in output.parents:
        raise ValueError("output cannot be nested in source")
    output.mkdir(parents=True, exist_ok=False)
    for item in source.iterdir():
        if item.is_symlink():
            raise ValueError("source symlink is not an acquisition file")
        if item.is_dir():
            if item.name not in DERIVED_DIRS:
                shutil.copytree(item, output / item.name, symlinks=False)
        elif item.is_file():
            if item.name not in DERIVED_FILES and not item.name.startswith("source-"):
                shutil.copy2(item, output / item.name)
    for name in ("capture-index.json", "frame-map.json", "raw.mkv",
                 "construction.json", "candidate-selection.json"):
        if not (output / name).is_file():
            raise ValueError("source-only acquisition missing " + name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    stage(args.source, args.output)


if __name__ == "__main__":
    main()
