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


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(candidate, source, receipt, *, tamper=False):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
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
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--source', required=True)
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--tamper', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate, args.source, args.receipt,
                           tamper=args.tamper)))
