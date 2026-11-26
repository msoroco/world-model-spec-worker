"""Exercise parked-light physical outcome branches on synthetic saved sources."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from analysis import measure
from parked_lamps import SCENE_SOURCES
from source_packet import sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def run(case_id, kind, attempt, output):
    if kind not in KINDS or case_id not in {
            item['case_id'] for item in json.loads((HERE / 'case-plan.json').read_text())['cases']}:
        raise ValueError('exact parked-light case or physical fixture kind missing')
    runtime_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if ROOT / '.runtime-work' not in runtime_root.parents:
        raise ValueError('SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work')
    attempt = Path(attempt)
    if ROOT / '.runtime-work' not in attempt.resolve().parents:
        raise ValueError('physical fixture source must be under .runtime-work')
    scratch = ROOT / '.runtime-work/c229398-physical-temp'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        stage = Path(temporary)
        names = ('config.json', 'construction.json', 'reviewed-packet.json',
                 'original-ticks.jsonl', 'trace.jsonl', 'video_frames.jsonl',
                 'fixture-provenance.json') + tuple(
                     name + '.txt' for name in (*SCENE_SOURCES, 'map_opendrive'))
        for name in names:
            shutil.copyfile(attempt / name, stage / name)
        if kind == 'incomplete_motion':
            path = stage / 'original-ticks.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[-1]['speed_mps'] = 3.0
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        elif kind == 'missing_evidence':
            (stage / 'parking_lawfulness.txt').unlink()
        measured, error, status = None, None, 'unverified'
        try:
            _, _, _, measured, _, _, _ = measure(stage)
            status = 'met'
        except ValueError as failure:
            error = str(failure)
            if kind == 'incomplete_motion' and 'did not remain parked' in error:
                status = 'not_met'
            elif kind != 'missing_evidence' or 'Missing required source' not in error:
                raise
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('parked-light physical branch outcome differs: ' + kind)
        result = {'case_id': case_id,
                  'physical_checks': {'maneuver': {
                      'status': status,
                      'method': 'source-bound original vehicle parking and lamp readback',
                      'sources': {name: sha(stage / name) for name in
                                  ('reviewed-packet.json', 'original-ticks.jsonl',
                                   'parking_lawfulness.txt') if (stage / name).is_file()},
                      'error': error, 'physical_causation_claimed': False}},
                  'maneuver_completed': status == 'met',
                  'realized_observables': {} if measured is None else {
                      'parked_frame_count': {'value': len(measured),
                                             'unit': 'frame',
                                             'method': 'saved original 20 Hz tick readback',
                                             'statistic': 'stationary interval samples',
                                             'time_window': 'parked interval',
                                             'reference': 'original-ticks.jsonl'}},
                  'provenance_kind': 'synthetic_fixture',
                  'diagnostic_fixture': True,
                  'physical_acceptance_claimed': False,
                  'legal_judgment': None}
        Path(output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
        lifecycle = None
        if kind == 'complete_motion':
            sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
            from worker_exchange.native_output import seal_capture
            from worker_exchange.saved_processing import (
                acknowledge_owner_release, copy_sources, record_native_exit)
            (stage / 'runner.py').write_text((HERE / 'runner.py').read_text())
            (stage / 'acquisition-provenance.json').write_text(json.dumps({
                'provenance_kind': 'synthetic_fixture',
                'diagnostic_fixture': True,
                'physical_acceptance_claimed': False}) + '\n')
            seal = seal_capture(stage, frames=9,
                                restoration={'restored': True,
                                             'settings_readback': 'synthetic CPU closure fixture'},
                                errors=[], encoder_exit_codes={'fixture': 0})
            exit_receipt = record_native_exit(stage)
            owner = acknowledge_owner_release(stage, stage / 'owner-release.json', True)
            with tempfile.TemporaryDirectory(dir=scratch) as saved:
                copy_sources(stage, Path(saved))
            if (exit_receipt['capture_seal_sha256'] != sha(stage / 'capture-seal.json') or
                    owner['native_exit_sha256'] != sha(stage / 'native-exit.json')):
                raise ValueError('Native lifecycle closure differs')
            lifecycle = seal['events'] + ['native_exit', 'owner_released',
                                          'saved_processing_started']
        return {'case_id': case_id, 'kind': kind, 'status': status,
                'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
                'lifecycle': lifecycle}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=KINDS, required=True)
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.attempt, args.output),
                     sort_keys=True))
