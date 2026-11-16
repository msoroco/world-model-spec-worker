"""Mock-only CPU proof of the six ordered capture-to-processing events.

No CARLA process or operator owner release occurs in this unit proof.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import post_capture
import runner

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit

EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def rejected(action, message):
    try:
        action()
    except (ValueError, FileNotFoundError) as error:
        assert message in str(error), str(error)
        return str(error)
    raise AssertionError('Lifecycle mutation accepted: ' + message)


def prove(case):
    assert case in {runner.PACKAGE.name + '__reference',
                    runner.PACKAGE.name + '__contrast'}
    manifest = runner.selected_manifest()
    with tempfile.TemporaryDirectory(prefix='c146314-lifecycle-mock-') as temp:
        folder = Path(temp)
        attempt = folder / 'attempt'
        output = folder / 'saved'
        subprocess.run([str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                        'materialize', '--manifest', str(manifest), '--case', case,
                        '--candidate', 'primary', '--output', str(attempt)],
                       cwd=ROOT, check=True, capture_output=True)
        write(attempt / 'acquisition-provenance.json',
              {'diagnostic_fixture': True, 'unit_mock': True})
        write(attempt / 'trace.jsonl', {'unit_mock': True})
        write(attempt / 'video_frames.jsonl', {'unit_mock': True})
        seal = seal_capture(attempt, frames=240, restoration={'restored': True},
                            errors=[], encoder_exit_codes={name: 0 for name in
                            ('overview', 'approach', 'reference_corner',
                             'driver_reference')})
        assert seal['diagnostic_fixture'] is True
        assert seal['events'] == EVENTS[:3]
        owner_path = attempt / 'operator-owner-release.json'
        args = (case, attempt, output, owner_path,
                ROOT / 'runtime/pipeline/library', folder / 'validator')
        negatives = {'before_native_exit': rejected(
            lambda: post_capture.command(*args, manifest=manifest),
            'Native capture seal or exit receipt missing')}
        exit_receipt = record_native_exit(attempt)
        assert exit_receipt['event'] == 'native_exit'
        negatives['before_owner_release'] = rejected(
            lambda: post_capture.command(*args, manifest=manifest),
            'Operator owner-release receipt missing')
        owner = {'event': 'owner_released', 'operator_attested': True,
                 'no_resource_operation_performed': True,
                 'native_construction_sha256': runner.sha(attempt / 'construction.json'),
                 'native_exit_sha256': runner.sha(attempt / 'native-exit.json'),
                 'unit_mock': True}
        write(owner_path, owner)
        planned = post_capture.command(*args, manifest=manifest)
        assert planned[planned.index('--owner-release-receipt') + 1] == str(owner_path)
        altered = {**owner, 'native_exit_sha256': '0' * 64}
        write(owner_path, altered)
        negatives['wrong_native_exit'] = rejected(
            lambda: post_capture.command(*args, manifest=manifest),
            'Operator release is absent or bound to another Native exit')
        write(owner_path, owner)

        def fake_process(command, **kwargs):
            assert command == planned
            receipt_path = output / 'v0001/processing.json'
            receipt_path.parent.mkdir(parents=True)
            write(receipt_path, {'case_id': case, 'candidate_id': 'primary',
                                 'passed': True, 'recorded_only': True,
                                 'originals_preserved': True,
                                 'missing_evidence': False,
                                 'events': ['saved_processing_started',
                                            'selected_analysis_executed',
                                            'originals_verified'],
                                 'unit_mock': True})

        with patch.object(post_capture.subprocess, 'run', fake_process):
            processing = post_capture.execute(*args, manifest=manifest)
        events = seal['events'] + [exit_receipt['event'], owner['event'],
                                   processing['events'][0]]
        assert events == EVENTS
        return {'format': 'c146314-six-event-lifecycle-cpu-proof-v1',
                'case_id': case, 'events': events, 'passed': True,
                'negative_rejections': negatives, 'mock_only': True,
                'original_carla_executed': False,
                'operator_owner_release_actually_attested': False,
                'saved_processing_actually_run': False,
                'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.case), sort_keys=True))
