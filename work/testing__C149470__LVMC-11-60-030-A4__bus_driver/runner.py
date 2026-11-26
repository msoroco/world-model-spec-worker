"""CPU-only check of one exact bus loading construction."""
import argparse
import importlib
import json
import os
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--site', type=Path)
    parser.add_argument('--adapter-module')
    args = parser.parse_args()
    scene = check()
    config = json.loads((Path(__file__).resolve().parent / 'config.json').read_text())
    if args.check:
        print('diagnostic CPU check passed: ' + scene['case_id'])
        return
    site = args.site or os.environ.get('C149470_REVIEWED_SITE')
    if not site or not args.output_dir:
        raise ValueError('reviewed original site and output directory required')
    module_name = args.adapter_module or os.environ.get('C149470_NATIVE_ADAPTER_MODULE')
    if not module_name:
        raise ValueError('Native adapter module required')
    adapter = importlib.import_module(module_name).create_adapter(scene['case_id'])
    from native_capture import capture
    print(json.dumps(capture(adapter, Path(site), config['case']['kind'],
                             Path(args.output_dir),
                             config.get('candidate_id', 'primary')), sort_keys=True))


if __name__ == '__main__':
    main()
