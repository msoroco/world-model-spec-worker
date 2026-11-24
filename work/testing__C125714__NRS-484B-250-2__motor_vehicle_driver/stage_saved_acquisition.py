"""Copy only sealed acquisition and construction inputs for saved-only replay.

Compatibility output contains derived analysis, render and converter products.
The saved processor must rebuild those outputs from a separate source-only tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


DERIVED_FILES = {
    'analysis-report.json', 'compatibility-analysis.log', 'compatibility.json',
    'event_review.json', 'event_review.webm', 'event_review_encoder.log',
    'event_review_frames.jsonl', 'final-decode.json', 'four-view-receipt.json',
    'negative-analysis.log', 'result.json', 'review_label.txt',
    'review_measured_speed.ass', 'review_render.lock', 'raw.mkv',
}
DERIVED_DIRS = {'channels', 'converted', 'traffic_spec', 'tests'}


def stage(source: Path, output: Path, manifest: Path) -> None:
    source, output, manifest = source.resolve(strict=True), output.resolve(), manifest.resolve(strict=True)
    if '.runtime-work' not in output.parts or source == output or source in output.parents:
        raise ValueError('source-only output must be a separate .runtime-work directory')
    if output.exists():
        raise ValueError('refusing to overwrite a saved acquisition')
    output.mkdir(parents=True)
    for item in source.iterdir():
        if item.is_symlink():
            raise ValueError('source symlink is not an acquisition file')
        if item.is_dir():
            if item.name not in DERIVED_DIRS:
                shutil.copytree(item, output / item.name, symlinks=False)
        elif item.is_file():
            if item.name not in DERIVED_FILES and not item.name.startswith('source-'):
                shutil.copy2(item, output / item.name)
    for name in ('construction.json', 'candidate-selection.json', 'config.json',
                 'original-bindings.json', 'site-context.json', 'ego-body-history.jsonl',
                 'other-body-history.jsonl', 'video_frames.jsonl', 'capture'):
        if not (output / name).exists():
            raise ValueError('source-only acquisition missing ' + name)
    selection_path = output / 'candidate-selection.json'
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    selection['manifest_sha256'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    selection_path.write_text(json.dumps(selection, indent=2) + '\n', encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    stage(args.source, args.output, args.manifest)


if __name__ == '__main__':
    main()
