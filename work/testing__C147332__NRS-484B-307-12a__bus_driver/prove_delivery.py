"""Exercise independent delivery audit on exact synthetic case sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
ORIGINALS = ('road.xodr', 'trace.jsonl', 'video_frames.jsonl', 'carla_recorder.log',
             'bus-body-history.jsonl', 'lane-signal-history.jsonl',
             'sign-state-original.jsonl', 'camera-frame-map.jsonl',
             'controller-history.jsonl', 'reviewed-context.json',
             *(name + '.mkv' for name in CAMERAS))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if not output_root.is_relative_to((REPO / '.runtime-work').resolve()):
        raise ValueError('SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work')
    destination = Path(args.output).resolve()
    if not destination.is_relative_to((REPO / '.runtime-work').resolve()):
        raise ValueError('diagnostic output must be under .runtime-work')
    sys.path.insert(0, str((REPO / 'runtime/scenario_pipeline').resolve()))
    from worker_exchange.fixture_recipe import materialize
    from delivery_audit import audit_attempt
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == args.case)
    construction = json.loads((ROOT / entry['construction']).read_text())
    materialize(REPO, REPO / entry['fixture_recipe'], destination)
    files = {item['path']: item['content'] for item in construction['files']}
    for name in ('scene.json', 'road.xodr'):
        (destination / name).write_text(files[name])
    (destination / 'carla_recorder.log').write_text('Synthetic diagnostic recorder placeholder; no Native execution\n')
    acquisition = json.loads((destination / 'acquisition.json').read_text())
    for name in ORIGINALS:
        acquisition[name] = sha(destination / name)
    write(destination / 'acquisition.json', acquisition)
    seal = {'format': 'worker-sealed-capture', 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True, 'frames': 5,
            'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
            'restoration': {'restored': True},
            'encoder_exit_codes': {name: 0 for name in CAMERAS},
            'sources': {name: (item['sha256'] if isinstance(item, dict) else item)
                        for name, item in acquisition.items()}}
    write(destination / 'capture-seal.json', seal)
    if args.mode == 'negative':
        (destination / 'lane-signal-history.jsonl').unlink()
        audit_attempt(destination, diagnostic=True)
        raise AssertionError('missing required signal source was accepted')
    audit = audit_attempt(destination, diagnostic=True)
    if audit['decoded_frames'] != {name: 5 for name in CAMERAS}:
        raise AssertionError('full four-camera decode was not proven')
    try:
        audit_attempt(destination)
    except ValueError as error:
        if 'original Native acquisition required' not in str(error):
            raise
    else:
        raise AssertionError('synthetic fixture was accepted as Native')
    kind = args.case.rsplit('__', 1)[-1]
    write(ROOT / f'delivery-{kind}-diagnostic-result.json', audit)
    print(args.case, 'diagnostic original-source audit and Native guard passed')


if __name__ == '__main__':
    main()
