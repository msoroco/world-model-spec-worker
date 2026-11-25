"""CPU-only check of one exact bus loading construction."""
import argparse
import json
from pathlib import Path

from bus_curb import CASES, validate_scene


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text())
    scene = json.loads((root / 'scene.json').read_text())
    case = next(c for c in CASES if c.name == config['case']['kind'])
    if config['selected_case_id'] != scene['case_id']:
        raise ValueError('selected case differs from scene')
    if config['rate_hz'] != 20 or config['duration_s'] != 45:
        raise ValueError('original capture timing changed')
    validate_scene(scene, case)
    if scene.get('source_kind') != 'synthetic_diagnostic_fixture':
        raise ValueError('diagnostic bundle source identity changed')
    return scene


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    scene = check()
    if not args.check:
        raise ValueError('Diagnostic source cannot authorize Native capture')
    print('diagnostic CPU check passed: ' + scene['case_id'])
