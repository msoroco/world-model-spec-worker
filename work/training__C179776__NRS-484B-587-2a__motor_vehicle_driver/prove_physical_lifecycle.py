"""CPU source-shaped motion and closure tests; never claims original Native capture."""

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile

ASSIGNMENT = 'training__C179776__NRS-484B-587-2a__motor_vehicle_driver'


def run(case, kind, output):
    repo = Path(__file__).resolve().parents[2]
    folder = repo / 'work' / ASSIGNMENT
    scratch = repo / '.runtime-work' / 'c179776-physical'
    scratch.mkdir(parents=True, exist_ok=True)
    root_env = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if repo / '.runtime-work' not in root_env.parents:
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    import sys
    sys.path.insert(0, str(repo / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.native_output import physical_result, seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure

    suffix = case.removeprefix(ASSIGNMENT + '__')
    if suffix not in ('probe_a', 'probe_b') or case != ASSIGNMENT + '__' + suffix:
        raise ValueError('Exact selected case required')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='physical-') as temp:
        attempt = Path(temp)
        for src, dst in ((folder / 'selected-candidates' / suffix / 'primary' / 'construction.json', 'construction.json'),
                         (folder / 'runner.py', 'runner.py'),
                         (folder / 'diagnostic-source' / suffix / 'trace.jsonl', 'trace.jsonl'),
                         (folder / 'diagnostic-source' / suffix / 'video_frames.jsonl', 'video_frames.jsonl')):
            shutil.copy2(src, attempt / dst)
        construction = json.loads((attempt / 'construction.json').read_text())
        config = next(json.loads(f['content']) for f in construction['files'] if f['path'] == 'config.json')
        (attempt / 'config.json').write_text(json.dumps(config, sort_keys=True) + '\n')
        (attempt / 'acquisition-provenance.json').write_text(json.dumps({'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
        if kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            if kind == 'incomplete_motion':
                rows = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines()]
                first = rows[0]['position_m']
                for row in rows:
                    row['position_m'] = first
                    row['position'] = {'x': first[0], 'y': first[1], 'z': first[2]}
                    row['velocity_mps'] = [0, 0, 0]
                    row['speed_mps'] = 0
                    row['speed_mph'] = 0
                (attempt / 'trace.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
            if kind == 'missing_evidence':
                (attempt / 'trace.jsonl').unlink()
            result = physical_result(attempt, {'case_id': case, 'target_checks': []})
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            assert result['physical_checks']['maneuver']['status'] == expected
            assert result['maneuver_completed'] is (expected == 'met')
            assert result['provenance_kind'] == 'synthetic_fixture' and result['diagnostic_fixture'] is True
            output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
            return {'case_id': case, 'kind': kind, 'motion_status': expected,
                    'synthetic_fixture': True, 'original_native_claimed': False}
        if kind != 'lifecycle':
            raise ValueError('Unknown physical proof kind')
        seal = seal_capture(attempt, frames=600, restoration={'restored': True}, errors=[],
                            encoder_exit_codes={name: 0 for name in ('overview', 'approach',
                            'reference_corner', 'driver_reference')},
                            context={'synthetic_lifecycle_test': True})
        assert seal['events'] == ['capture_finished', 'encoders_closed', 'restoration_verified']
        record_native_exit(attempt)
        try:
            _closure(attempt, None, 'native', False)
        except ValueError as error:
            assert 'owner-release' in str(error)
        else:
            raise AssertionError('Saved processing permitted before owner release')
        owner = attempt / 'owner-release.json'
        acknowledge_owner_release(attempt, owner, True)
        _closure(attempt, owner, 'native', False)
        saved = json.loads((folder / f'selected-saved-{suffix}-primary.json').read_text())
        assert saved['passed'] is True and saved['recorded_only'] is True
        assert 'saved_processing_started' in saved['events']
        events = [*seal['events'], 'native_exit', 'owner_released', 'saved_processing_started']
        output.write_text(json.dumps({'case_id': case, 'events': events,
                                      'synthetic_lifecycle_test': True,
                                      'owner_release_required': True,
                                      'saved_processing_receipt': f'selected-saved-{suffix}-primary.json'},
                                     indent=2, sort_keys=True) + '\n')
        return {'case_id': case, 'kind': kind, 'events': events,
                'synthetic_fixture': True, 'original_native_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                          'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, Path(args.output).resolve()), sort_keys=True))
