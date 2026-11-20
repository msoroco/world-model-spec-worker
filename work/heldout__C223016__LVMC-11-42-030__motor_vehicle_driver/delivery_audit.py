"""Independent CPU audit of one C223016 saved diagnostic case.

This verifies source continuity and candidate identity. It cannot verify the
physical or municipal direction premise used by the diagnostic fixture.
"""

import argparse
import hashlib
import json
from math import hypot
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
CAMERAS = {'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv'}


def physical_fixture(kind, config_name='config.json'):
    """Exercise the runtime completion criterion with labelled synthetic rows."""
    sys.path.insert(0, str(HERE.parents[1] / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.native_output import assess_physical, default_descriptor
    config = json.loads((HERE / config_name).read_text())
    criterion = default_descriptor(config)
    if criterion['criterion'] != 'travel_progress':
        raise ValueError('Physical fixture requires the authored progress criterion')
    frames = config['frames']
    progress = criterion['minimum_progress_m'] * (1.5 if kind == 'complete' else .1)
    with TemporaryDirectory(prefix='c223016-physical-', dir=HERE.parents[1] / '.runtime-work') as temporary:
        root = Path(temporary)
        (root / 'config.json').write_text(json.dumps(config))
        (root / 'video_frames.jsonl').write_text(''.join(json.dumps({
            'carla_frame': 1000 + index, 'time_s': index / config['rate_hz']}) + '\n'
            for index in range(frames)))
        if kind != 'missing':
            (root / 'trace.jsonl').write_text(''.join(json.dumps({
                'frame': 1000 + index, 'time_s': index / config['rate_hz'],
                'position_m': [progress * index / (frames - 1), 0]}) + '\n'
                for index in range(frames)))
        assessment = assess_physical(root, config)
        expected = {'complete': 'met', 'incomplete': 'not_met',
                    'missing': 'unverified'}[kind]
        observed = assessment['physical_checks']['maneuver']['status']
        if observed != expected:
            raise ValueError(f'Physical fixture expected {expected}; got {observed}')
        return {'fixture_kind': kind, 'expected': expected, 'observed': observed,
                'provenance_kind': 'synthetic_fixture', 'actual_native_capture': False,
                'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def physical_result_fixture(kind, output, config_name='config.json'):
    """Write the measured source-bound diagnostic result for one exact config."""
    sys.path.insert(0, str(HERE.parents[1] / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.native_output import assess_physical, default_descriptor
    config_path = Path(config_name)
    config = json.loads(config_path.read_text())
    descriptor = default_descriptor(config)
    if descriptor['criterion'] != 'travel_progress':
        raise ValueError('Unexpected physical criterion')
    frames = config['frames']
    distance = descriptor['minimum_progress_m'] * (
        1.5 if kind == 'complete_motion' else .1)
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown fixture kind')
    with TemporaryDirectory(prefix='c223016-physical-',
                            dir=HERE.parents[1] / '.runtime-work') as temporary:
        root = Path(temporary)
        (root / 'config.json').write_text(json.dumps(config) + '\n')
        (root / 'video_frames.jsonl').write_text(''.join(json.dumps({
            'carla_frame': 1000 + index, 'time_s': index / config['rate_hz']}) + '\n'
            for index in range(frames)))
        if kind != 'missing_evidence':
            (root / 'trace.jsonl').write_text(''.join(json.dumps({
                'frame': 1000 + index, 'time_s': index / config['rate_hz'],
                'position_m': [distance * index / (frames - 1) *
                               config['subject_direction_xy'][0],
                               distance * index / (frames - 1) *
                               config['subject_direction_xy'][1]]}) + '\n'
                for index in range(frames)))
        assessment = assess_physical(root, config)
    status = assessment['physical_checks']['maneuver']['status']
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if status != expected:
        raise ValueError(f'{kind}: measured {status}, expected {expected}')
    result = {'case_id': config['selected_case_id'], 'fixture_kind': kind,
              'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
              'actual_native_capture': False,
              'physical_acceptance_claimed': False,
              'legal_acceptance_claimed': False,
              'physical_checks': assessment['physical_checks'],
              'maneuver_completed': assessment['maneuver_completed'],
              'realized_observables': assessment['realized_observables']}
    Path(output).write_text(json.dumps(result, indent=2) + '\n')
    return status


def lifecycle_fixture(case_id):
    """Exercise the ordered synthetic capture and saved-processing protocol."""
    import os
    from worker_exchange.fixture_recipe import materialize as make_fixture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.runtime_cli import materialize as make_attempt
    from worker_exchange.saved_processing import (
        acknowledge_owner_release, copy_sources, record_native_exit,
        run as process_saved)
    root = HERE.parents[1]
    os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                          str(root / '.runtime-work/c223016-physical-output'))
    manifest = HERE / 'execution-manifest.json'
    entry = next(item for item in json.loads(manifest.read_text())['cases']
                 if item['case_id'] == case_id)
    events = ['capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started']
    with TemporaryDirectory(prefix='c223016-lifecycle-',
                            dir=root / '.runtime-work') as temporary:
        base = Path(temporary)
        make_fixture(root, root / entry['fixture_recipe'], base / 'fixture')
        make_attempt(manifest, case_id, base / 'attempt')
        copy_sources(base / 'fixture', base / 'attempt')
        attempt = base / 'attempt'
        construction = json.loads((HERE / entry['construction']).read_text())
        (attempt / 'runner.py').write_text(
            (attempt / construction['entrypoint']).read_text())
        (attempt / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'fixture_scope': 'synthetic lifecycle protocol only'}) + '\n')
        frames = len((attempt / 'video_frames.jsonl').read_text().splitlines())
        seal = seal_capture(attempt, frames=frames,
                            restoration={'restored': True}, errors=[],
                            encoder_exit_codes={name: 0 for name in
                                ('overview', 'approach', 'reference_corner',
                                 'driver_reference')},
                            context={'fixture_scope':
                                     'synthetic lifecycle protocol only'})
        if seal['events'] != events[:3] or not seal['diagnostic_fixture']:
            raise ValueError('Capture closure order or fixture scope differs')
        if record_native_exit(attempt)['event'] != events[3]:
            raise ValueError('Native exit event missing')
        owner = base / 'owner-release.json'
        if acknowledge_owner_release(attempt, owner, True)['event'] != events[4]:
            raise ValueError('Owner release event missing')
        process_saved(manifest, case_id, attempt, base / 'processing',
                      root / 'runtime/library',
                      root / '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck',
                      owner_receipt=owner)
        receipt = json.loads((base / 'processing/v0001/processing.json').read_text())
        if not receipt.get('passed') or not receipt.get('originals_preserved'):
            raise ValueError('Saved processing did not pass after closure')
        print(' '.join(events))
        print(case_id, 'synthetic_lifecycle_only', 'saved_processing_passed')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(candidate, source, receipt, *, tamper=False, manifest_override=None):
    manifest = json.loads(Path(manifest_override or HERE / 'execution-manifest.json').read_text())
    receipt = json.loads(Path(receipt).read_text())
    entry = next(item for item in manifest['cases']
                 if item['case_id'] == receipt.get('case_id'))
    selected = entry if candidate == 'primary' else next(
        item for item in entry['candidates'] if item['id'] == candidate)
    if (receipt.get('case_id') != entry['case_id'] or
            receipt.get('candidate_id') != candidate or
            receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('physical_acceptance_claimed') is not False or
            receipt.get('legal_acceptance_claimed') is not False or
            receipt.get('native_revision', {}).get('construction_sha256') !=
            selected['construction_sha256']):
        raise ValueError('Saved status, candidate or construction differs')
    hashes = receipt['original_source_hashes']
    if not CAMERAS <= hashes.keys():
        raise ValueError('Four original camera hashes required')
    for name, expected in hashes.items():
        observed = digest(Path(source) / name)
        if tamper and name == 'direction_state.jsonl':
            observed = '0' * 64
        if observed != expected:
            raise ValueError('Original source hash differs: ' + name)
    direction = [json.loads(line) for line in
                 (Path(source) / 'direction_state.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in
             (Path(source) / 'trace.jsonl').read_text().splitlines()]
    config = json.loads((Path(source) / 'config.json').read_text())
    if len(direction) != len(trace) or len(direction) < 2:
        raise ValueError('Original direction/trace frame count differs')
    for observed, traced in zip(direction, trace):
        if (observed['frame'], observed['time_s']) != (traced['frame'], traced['time_s']):
            raise ValueError('Original direction/trace frame join differs')
        if (observed['lane_id'] != config['governed_lane_id'] or
                observed['device']['governs_lane_id'] != config['governed_lane_id']):
            raise ValueError('Governed Native lane identity differs')
        a, b = observed['subject_velocity_xy'], traced['velocity_mps'][:2]
        length = hypot(*a) * hypot(*b)
        if length < .01 or sum(x * y for x, y in zip(a, b)) / length < .95:
            raise ValueError('Direction stream disagrees with retained trace velocity')
    result = Path(receipt['result'])
    if digest(result) != receipt['result_sha256']:
        raise ValueError('Saved result hash differs')
    analysis = json.loads(result.read_text())
    if (analysis.get('case_id') != entry['case_id'] or
            analysis.get('physical_acceptance_claimed') is not False or
            analysis.get('legal_acceptance_claimed') is True):
        raise ValueError('Saved result identity or status differs')
    return {'candidate_id': candidate, 'case_id': entry['case_id'],
            'original_source_count': len(hashes), 'joined_direction_frames': len(direction),
            'source_hashes_verified': True, 'saved_result_verified': True,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False,
            'scope': 'synthetic diagnostic software proof'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--physical-kind')
    parser.add_argument('--physical-config')
    parser.add_argument('--physical-output')
    parser.add_argument('--lifecycle-case')
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--source')
    parser.add_argument('--receipt')
    parser.add_argument('--tamper', action='store_true')
    args = parser.parse_args()
    if args.lifecycle_case:
        sys.path.insert(0, str(HERE.parents[1] / 'runtime' / 'scenario_pipeline'))
        lifecycle_fixture(args.lifecycle_case)
        sys.exit(0)
    if args.physical_kind:
        print(physical_result_fixture(args.physical_kind, args.physical_output,
                                      args.physical_config))
        sys.exit(0)
    if not args.source or not args.receipt:
        parser.error('--source and --receipt are required for the source audit')
    print(json.dumps(audit(args.candidate, args.source, args.receipt,
                           tamper=args.tamper)))
