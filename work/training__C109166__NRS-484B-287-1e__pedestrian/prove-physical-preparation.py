"""Synthetic CPU exercise of reviewed, incomplete, and missing source outcomes."""
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from finalize import diagonal_entry_measurement, reviewed_physical_status


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run_case(index):
    suffix = f'controlled_{index}'
    case = HERE.name + '__' + suffix
    construction_path = HERE / 'cases' / suffix / 'primary/construction.json'
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    diagnostic = json.loads((HERE / f'diagnostic-{suffix}.json').read_text())
    scratch = ROOT / '.runtime-work'
    output = HERE / 'cases' / suffix
    fixtures = []
    with tempfile.TemporaryDirectory(dir=scratch, prefix='c109166-physical-') as temporary:
        folder = Path(temporary)
        for name in ('video_frames.jsonl', 'pedestrian-original.jsonl',
                     'device-original.jsonl', 'camera-sources.jsonl'):
            (folder / name).write_text(diagnostic['files'][name])
        write(folder / 'config.json', config)
        claims = {'authorization': 'diagonal_crossing_authorized',
                  'official_status': 'official_device',
                  'movement_applicability': 'governs_exact_diagonal_movement'}
        receipt = {}
        for name, claim in claims.items():
            media = folder / (name + '.png')
            media.write_bytes(('synthetic test media: ' + name).encode())
            document = {'provenance_kind': 'original_survey',
                        'review_status': 'independently_reviewed',
                        'independent_reviewer': 'synthetic CPU protocol test',
                        'native_head_id': config['opendrive_signal_id'],
                        'device_id': 'c109166-diagonal-crossing-head',
                        'movement_id': 'c109166-diagonal-sw-ne', claim: True,
                        'original_survey_media': {'path': media.name, 'sha256': sha(media)}}
            source = folder / (name + '.json')
            write(source, document)
            receipt[name] = {'path': source.name, 'sha256': sha(source),
                             'device_id': 'c109166-diagonal-crossing-head',
                             'movement_id': 'c109166-diagonal-sw-ne',
                             'review_status': 'pending_independent_review'}
        write(folder / 'authority-receipt.json', receipt)
        for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            (folder / (camera + '.mkv')).write_bytes(('synthetic camera bytes: ' + camera).encode())
        measured = diagonal_entry_measurement(folder)
        source_hashes = {name: sha(folder / name) for name in
                         ('video_frames.jsonl', 'pedestrian-original.jsonl', 'device-original.jsonl')}
        video_hashes = {camera: sha(folder / (camera + '.mkv')) for camera in
                        ('overview', 'approach', 'reference_corner', 'driver_reference')}
        write(folder / 'diagonal-pixel-review.json', {
            'review_status': 'independently_reviewed',
            'independent_reviewer': 'synthetic CPU protocol test',
            'frame_map_sha256': source_hashes['video_frames.jsonl'],
            'first_entry_native_frame': measured['first_entry_native_frame'],
            'actual_diagonal_instruction': measured['first_entry_instruction'],
            'source_video_sha256': video_hashes})
        people = [json.loads(line) for line in (folder / 'pedestrian-original.jsonl').read_text().splitlines()]
        length = sum(math.dist(a['center_xy_m'], b['center_xy_m'])
                     for a, b in zip(people, people[1:]))
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            if kind == 'missing_evidence':
                (folder / 'device-original.jsonl').unlink()
                try:
                    diagonal_entry_measurement(folder)
                except ValueError as error:
                    if 'device-original.jsonl' not in str(error):
                        raise
                    detail = str(error)
                else:
                    raise ValueError('missing original device source accepted')
                checks = {'maneuver': {'status': 'unverified',
                                      'method': 'selected original source missing',
                                      'sources': {'pedestrian-original.jsonl': sha(folder / 'pedestrian-original.jsonl')},
                                      'reason': detail}}
            else:
                write(folder / 'road-boundary-review.json', {
                    'review_status': 'independently_reviewed',
                    'independent_reviewer': 'synthetic CPU protocol test',
                    'source_sha256': source_hashes,
                    'first_entry_native_frame': measured['first_entry_native_frame'],
                    'clearance_native_frame': measured['first_entry_native_frame'] + 300,
                    'full_body_diagonal_clearance_observed': kind == 'complete_motion',
                    'authorized_diagonal_path_observed': kind == 'complete_motion'})
                checks = reviewed_physical_status(folder, measured)
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if checks['maneuver']['status'] != expected:
                raise ValueError('physical source outcome differs: ' + kind)
            result = {'case_id': case, 'physical_checks': checks,
                      'maneuver_completed': expected == 'met',
                      'realized_observables': {'synthetic_sampled_path_m': length} if expected == 'met' else {},
                      'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
            result_path = output / ('physical-' + kind + '-result.json')
            log_path = output / ('physical-' + kind + '.log')
            write(result_path, result)
            log_path.write_text(json.dumps({'case_id': case, 'kind': kind,
                                            'status': expected, 'passed': True}) + '\n')
            fixtures.append({'kind': kind,
                'command': 'prove-physical-preparation.py --case ' + case,
                'exit_code': 0, 'log': str(log_path.relative_to(HERE)),
                'log_sha256': sha(log_path), 'result': str(result_path.relative_to(HERE)),
                'result_sha256': sha(result_path)})
    events = ['capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started']
    lifecycle_log = output / 'physical-lifecycle.log'
    lifecycle_log.write_text(json.dumps({'events': events, 'synthetic_fixture': True}) + '\n')
    proof_path = output / 'physical-preparation.json'
    write(proof_path, {'format': 'c109166-physical-preparation-cpu-proof-v1',
                       'case_id': case, 'construction_sha256': sha(construction_path),
                       'fixtures': fixtures,
                       'lifecycle': {'events': events, 'exit_code': 0,
                                     'log': str(lifecycle_log.relative_to(HERE)),
                                     'log_sha256': sha(lifecycle_log)},
                       'original_native_executed': False})
    return {'case_id': case, 'receipt': str(proof_path.relative_to(HERE)),
            'sha256': sha(proof_path)}


def main():
    print(json.dumps({'proofs': [run_case(i) for i in (1, 2)]}))


if __name__ == '__main__':
    main()
