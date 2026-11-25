"""Exercise the pinned physical checker on synthetic 900-frame source shapes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def _lines(path, rows):
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


def run(case_id, kind, output):
    if kind not in KINDS or not case_id.startswith(PACKAGE.name + '__'):
        raise ValueError('Exact case or physical outcome differs')
    root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if REPO / '.runtime-work' not in root.parents and root != REPO / '.runtime-work':
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import physical_result, seal_capture
    from worker_exchange.saved_processing import (record_native_exit,
        acknowledge_owner_release, copy_sources)
    label = case_id.split('__')[-1]
    construction_path = PACKAGE / ('construction.json' if label == 'precedence'
                                   else f'cases/{label}/construction.json')
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    if config['selected_case_id'] != case_id:
        raise ValueError('Selected physical fixture case differs')
    scratch = REPO / '.runtime-work' / 'c125763-2501-physical-probe'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        stage = Path(directory)
        (stage / 'config.json').write_text(json.dumps(config) + '\n')
        (stage / 'construction.json').write_text(json.dumps(construction) + '\n')
        (stage / 'runner.py').write_text(next(item['content'] for item in
            construction['files'] if item['path'] == 'runner.py'))
        (stage / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False}) + '\n')
        mapping = [{'video_frame': i, 'carla_frame': 1000 + i,
                    'native_frame': 1000 + i, 'time_s': i * .05} for i in range(900)]
        _lines(stage / 'video_frames.jsonl', mapping)
        positions = [-10 + 20 * i / 899 if kind == 'complete_motion'
                     else -10 + i / 899 for i in range(900)]
        _lines(stage / 'trace.jsonl', [{'frame': 1000 + i, 'time_s': i * .05,
            'position_m': [x, 0.0, 0.0]} for i, x in enumerate(positions)])
        if kind != 'missing_evidence':
            _lines(stage / 'crossing_history.jsonl', [{'frame': 1000 + i,
                'time_s': i * .05,
                'ego_vertices_m': [[x - .4, -.4, 0.0], [x + .4, -.4, 0.0],
                                   [x + .4, .4, 0.0], [x - .4, .4, 0.0]]}
                for i, x in enumerate(positions)])
        result = {'case_id': case_id, 'target_checks': [{'target': 'synthetic crossing motion',
            'requested': kind, 'measured': kind, 'method': 'physical_probe',
            'tolerance': 0, 'matched': True, 'physical_cause_confirmed': False,
            'cause_evidence': 'synthetic source-shape only'}]}
        measured = physical_result(stage, result)
        measured['physical_acceptance_claimed'] = False
        measured['legal_verdict_claimed'] = False
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if measured['physical_checks']['maneuver']['status'] != expected:
            raise ValueError('Physical outcome differs: ' + kind)
        Path(output).write_text(json.dumps(measured, indent=2, allow_nan=False) + '\n')
        lifecycle = None
        if kind == 'complete_motion':
            seal = seal_capture(stage, frames=900,
                restoration={'restored': True, 'settings_readback': 'CPU protocol fixture'},
                errors=[], encoder_exit_codes={'diagnostic': 0})
            exit_receipt = record_native_exit(stage)
            owner = acknowledge_owner_release(stage, stage / 'owner-release.json', True)
            with tempfile.TemporaryDirectory(dir=scratch) as saved:
                copy_sources(stage, Path(saved))
            if (exit_receipt['capture_seal_sha256'] !=
                    hashlib.sha256((stage / 'capture-seal.json').read_bytes()).hexdigest()
                    or owner['native_exit_sha256'] !=
                    hashlib.sha256((stage / 'native-exit.json').read_bytes()).hexdigest()):
                raise ValueError('CPU lifecycle source binding failed')
            lifecycle = seal['events'] + ['native_exit', 'owner_released',
                                         'saved_processing_started']
        return {'case_id': case_id, 'kind': kind, 'maneuver': expected,
                'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
                'lifecycle': lifecycle}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=KINDS, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.output), sort_keys=True))


if __name__ == '__main__':
    main()
