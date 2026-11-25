"""Materialize a fresh exact package with retained diagnostic acquisition."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]


def run(label, compatibility, stage):
    suffix = 'entrant_can_occupy_gap' if label == 'wide' else 'entrant_cannot_occupy_gap'
    case_id = PACKAGE.name + '__' + suffix
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    subprocess.run([sys.executable, str(REPO / 'runtime.py'), 'materialize',
                    '--manifest', str(PACKAGE / 'execution-manifest.json'),
                    '--case', case_id, '--output', str(stage)],
                   cwd=REPO, env=env, check=True, stdout=subprocess.DEVNULL)
    recipe = json.loads((PACKAGE / 'cases' / (label + '-recipe.json')).read_text())
    specification = json.loads((PACKAGE / 'cases' / (label + '-diagnostic.json')).read_text())
    for item in recipe['sources']:
        relative = Path(item['path'])
        target = stage / relative
        if relative.parts[0] == 'capture':
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(compatibility / relative, target)
    shutil.copytree(compatibility / 'capture', stage / 'capture')
    for video in specification['videos']:
        relative = Path(video['path'])
        shutil.copyfile(compatibility / relative, stage / relative)
    shutil.copyfile(compatibility / 'raw.mkv', stage / 'raw.mkv')
    print(label, 'saved-only source staged', stage)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('label', choices=('wide', 'narrow'))
    parser.add_argument('compatibility', type=Path)
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    run(args.label, args.compatibility, args.stage)
