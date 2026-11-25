"""Synthetic CPU travel and Native ownership lifecycle proof for crest cases."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(path, config, construction, kind):
    path.mkdir()
    write(path / 'config.json', config)
    write(path / 'construction.json', construction)
    (path / 'runner.py').write_text(next(
        item['content'] for item in construction['files'] if item['path'] == 'runner.py'))
    write(path / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    if kind == 'missing_evidence':
        return
    xs = [float(3 * index) for index in range(9)] if kind == 'complete_motion' else [index / 10 for index in range(9)]
    rows = []
    mapping = []
    for index, x in enumerate(xs):
        rows.append({'frame': 200 + index, 'time_s': index / 20,
                     'position': {'x': x, 'y': 0, 'z': 0},
                     'position_m': [x, 0, 0], 'heading_deg': 0, 'speed_mps': 1})
        mapping.append({'video_frame': index, 'carla_frame': 200 + index,
                        'time_s': index / 20})
    (path / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    (path / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in mapping))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    from worker_exchange.native_output import physical_result, seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == args.case)
    construction = json.loads((HERE / entry['construction']).read_text())
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    suffix = args.case.rsplit('__', 1)[-1]
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    for kind, expected in [('complete_motion', 'met'), ('incomplete_motion', 'not_met'),
                           ('missing_evidence', 'unverified')]:
        folder = root / kind
        fixture(folder, config, construction, kind)
        result = physical_result(folder, {'target_checks': [{
            'target': 'original-shaped crest travel progression', 'requested': True,
            'measured': kind == 'complete_motion', 'method': 'synthetic trace progress',
            'tolerance': 0, 'matched': kind == 'complete_motion',
            'physical_cause_confirmed': False, 'cause_evidence': 'synthetic trace only'}]})
        if result['physical_checks']['maneuver']['status'] != expected:
            raise ValueError('synthetic physical fixture result mismatch')
        write(HERE / f'physical-{suffix}-{kind}.json', result)
        print(kind, expected)
    complete = root / 'complete_motion'
    seal = seal_capture(complete, frames=9,
        restoration={'restored': True, 'settings_readback': 'CPU protocol fixture'},
        errors=[], encoder_exit_codes={'diagnostic': 0})
    exit_receipt = record_native_exit(complete)
    owner = acknowledge_owner_release(complete, complete / 'owner-release.json', True)
    stage = root / 'saved_stage'
    stage.mkdir()
    copy_sources(complete, stage)
    if exit_receipt['capture_seal_sha256'] != sha(complete / 'capture-seal.json') or owner['native_exit_sha256'] != sha(complete / 'native-exit.json'):
        raise ValueError('Native lifecycle source binding failed')
    print('lifecycle', *seal['events'], 'native_exit', 'owner_released', 'saved_processing_started')


if __name__ == '__main__':
    main()
