"""Stage immutable diagnostic acquisition for saved-only replay tests."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil

DERIVED = ('original_actor_state.jsonl', 'original_four_view_frame_map.jsonl',
           'headlamp_emission_and_aim_review.jsonl', 'reviewed-site-geometry.json',
           'candidate-selection.json')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--target', required=True)
    args = parser.parse_args()
    source = Path(args.source).resolve(strict=True)
    target = Path(args.target).resolve()
    scratch = (Path.cwd() / '.runtime-work').resolve(strict=True)
    if not target.is_relative_to(scratch) or target.exists():
        raise ValueError('saved fixture must be fresh under .runtime-work')
    shutil.copytree(source, target, copy_function=os.link)
    for name in DERIVED:
        (target / name).unlink(missing_ok=True)
    print('staged source-only parked-headlamp diagnostic attempt:', target)


if __name__ == '__main__':
    main()
