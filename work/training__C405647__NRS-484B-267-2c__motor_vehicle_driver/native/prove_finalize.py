"""Synthetic positive and fail-closed checks for the saved-source finalizer."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
from finalize import finalize
from measure_readiness import CAMERAS
from scene import request


def main():
    if '.runtime-work' not in Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).parts:
        raise ValueError('Export output root under .runtime-work before importing runtime')
    source = REPO / '.runtime-work' / 'C405647-readiness-proof'
    materialized = REPO / '.runtime-work' / 'c405647-available-primary-v7'
    scratch = REPO / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='c405647-finalize-', dir=scratch))
    try:
        for name in ('config.json', 'construction.json'):
            shutil.copyfile(materialized / name, attempt / name)
        for name in ('video_frames.jsonl', 'approach_trace.jsonl', 'emergency_review.json',
                     *(camera + '.mkv' for camera in CAMERAS)):
            shutil.copyfile(source / name, attempt / name)
        (attempt / 'native-request.json').write_text(json.dumps(request('braking_capacity_available')) + '\n')
        shutil.copyfile(source / 'approach_trace.jsonl', attempt / 'trace.jsonl')
        output = attempt / 'saved-analysis.json'
        (attempt / 'approach_trace.jsonl').unlink()
        try:
            finalize(attempt, output)
        except ValueError as exc:
            assert 'Missing required source: approach_trace.jsonl' in str(exc)
        else:
            raise AssertionError('Missing saved motion accepted')
        shutil.copyfile(source / 'approach_trace.jsonl', attempt / 'approach_trace.jsonl')
        (attempt / 'native-request.json').write_text(json.dumps(request('not_available')) + '\n')
        try:
            finalize(attempt, output)
        except ValueError as exc:
            assert 'Exact saved case or candidate differs' in str(exc)
        else:
            raise AssertionError('Cross-case request accepted')
        (attempt / 'native-request.json').write_text(json.dumps(request('braking_capacity_available')) + '\n')
        report = finalize(attempt, output)
        assert report['physical_acceptance_claimed'] is False
        assert report['legal_verdict_claimed'] is False
        assert len(list((attempt / 'channels').glob('*.jsonl'))) == 6
        assert all(len(path.read_text().splitlines()) == 600 for path in
                   (attempt / 'channels').glob('*.jsonl'))
        result = json.loads((attempt / 'result.json').read_text())
        assert result['accepted'] is False and result['setup_confirmed'] is False
        try:
            finalize(attempt, output)
        except ValueError as exc:
            assert 'Retain original finalization' in str(exc)
        else:
            raise AssertionError('Overwritten finalization accepted')
        forged = Path(tempfile.mkdtemp(prefix='c405647-forged-original-', dir=scratch))
        try:
            for name in ('config.json', 'construction.json', 'native-request.json',
                         'video_frames.jsonl', 'approach_trace.jsonl', 'emergency_review.json',
                         'trace.jsonl', *(camera + '.mkv' for camera in CAMERAS)):
                shutil.copyfile(attempt / name, forged / name)
            try:
                with patch('finalize.measure', return_value=dict(
                        result['measured_values'], source_kind='original_source_review')):
                    finalize(forged, forged / 'saved-analysis.json')
            except ValueError as exc:
                assert 'Missing original capture source' in str(exc)
            else:
                raise AssertionError('Original claim without capture lifecycle accepted')
        finally:
            shutil.rmtree(forged)
        other = Path(tempfile.mkdtemp(prefix='c405647-finalize-unbraked-', dir=scratch))
        try:
            unavailable = REPO / '.runtime-work' / 'c405647-unavailable-primary-v7'
            for name in ('config.json', 'construction.json'):
                shutil.copyfile(unavailable / name, other / name)
            for name in ('video_frames.jsonl', 'approach_trace.jsonl', 'emergency_review.json',
                         *(camera + '.mkv' for camera in CAMERAS)):
                shutil.copyfile(source / name, other / name)
            rows = [json.loads(line) for line in (other / 'approach_trace.jsonl').read_text().splitlines()]
            for row in rows:
                row['ego_brake'] = 0
                row['ego_speed_mps'] = 15
            (other / 'approach_trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            shutil.copyfile(other / 'approach_trace.jsonl', other / 'trace.jsonl')
            (other / 'native-request.json').write_text(json.dumps(request('not_available')) + '\n')
            finalize(other, other / 'saved-analysis.json')
            unbraked = json.loads((other / 'result.json').read_text())
            assert unbraked['target_checks'][0]['requested'] == 0
            assert unbraked['target_checks'][0]['measured'] == 0
            assert unbraked['target_checks'][0]['matched'] is True
        finally:
            shutil.rmtree(other)
        print(json.dumps({'passed': True, 'case_id': result['case_id'],
                          'source_kind': result['provenance_kind'], 'channels': 6,
                          'frames_per_channel': 600, 'duplicate_rejected': True,
                          'missing_motion_rejected': True, 'cross_case_rejected': True,
                          'missing_original_capture_rejected': True,
                          'unbraked_case_passed': True,
                          'physical_acceptance_claimed': False,
                          'legal_verdict_claimed': False}))
    finally:
        shutil.rmtree(attempt)


if __name__ == '__main__':
    main()
