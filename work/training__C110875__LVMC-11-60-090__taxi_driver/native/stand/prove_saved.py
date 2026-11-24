"""Retain taxi source fixtures and prove positive/negative saved measurements."""
import copy
import json
import os
from pathlib import Path
import subprocess

from request import CASES, FRAMES, RATE, HERE
from saved import CAMERAS, process, sha

ROOT = HERE.parents[3]
OUT = ROOT / '.runtime-work' / 'c110875-saved-sources'


def put(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def create_media():
    media = OUT / 'media'
    media.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in CAMERAS:
        path = media / (name + '.mkv')
        result = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                                 '-y', '-f', 'lavfi', '-i',
                                 'color=c=black:s=32x32:r=20', '-frames:v', str(FRAMES),
                                 '-c:v', 'ffv1', str(path)], capture_output=True,
                                text=True, timeout=120)
        if result.returncode:
            raise RuntimeError('Diagnostic camera encoding failed: ' + result.stderr)
        hashes[path.name] = sha(path)
    return hashes


def fixture(suffix, media_hashes):
    bundle = HERE / 'drafts' / suffix
    folder = OUT / suffix
    folder.mkdir(parents=True, exist_ok=True)
    request = [json.loads(x) for x in (bundle / 'requested-tracks.jsonl').read_text().splitlines()]
    raw = []
    frames = []
    for index, row in enumerate(request):
        raw.append({'frame': index, 'native_frame': 1000 + index,
                    'time_s': row['time_s'], 'source_kind': 'synthetic_fixture',
                    'actor_id': 107, 'blueprint': 'vehicle.tesla.model3',
                    'ego_xy_m': [row['requested_x_m'], row['requested_y_m']],
                    'heading_deg': row['requested_heading_deg'],
                    'requested_x_m': row['requested_x_m'],
                    'requested_y_m': row['requested_y_m'],
                    'requested_heading_deg': row['requested_heading_deg'],
                    'stand_designation_verified': False,
                    'posted_notice_verified': False,
                    'taxi_license_verified': False,
                    'first_intersection_native_verified': False,
                    'legal_verdict': None})
        frames.append({'video_frame': index, 'native_frame': 1000 + index,
                       'time_s': row['time_s']})
    raw_path = folder / 'native-actors.jsonl'
    frames_path = folder / 'video_frames.jsonl'
    raw_path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in raw))
    frames_path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in frames))
    for name in CAMERAS:
        target = folder / (name + '.mkv')
        if target.exists():
            target.unlink()
        os.link(OUT / 'media' / target.name, target)
    review = {'source_kind': 'synthetic_fixture', 'case_id': HERE.parents[1].name + '__' + suffix,
              'candidate_id': 'primary', 'native_actors_sha256': sha(raw_path),
              'video_frames_sha256': sha(frames_path), 'media_sha256': media_hashes,
              'sign_or_stand_authority_reviewed': False}
    put(folder / 'review.json', review)
    return bundle, folder


def main():
    media_hashes = create_media()
    records = []
    negatives = []
    for suffix in CASES:
        bundle, folder = fixture(suffix, media_hashes)
        measured = process(bundle, folder, synthetic=True)
        if not measured['turn_request_matched'] or measured['delivery_ready']:
            raise AssertionError('Exact taxi source measurement failed')
        records.append({'case_id': measured['case_id'],
                        'requested_tracks_sha256': sha(bundle / 'requested-tracks.jsonl'),
                        'source_sha256': {name: sha(folder / name) for name in
                            ('native-actors.jsonl', 'video_frames.jsonl', 'review.json')},
                        'measurement': measured})
        raw_path = folder / 'native-actors.jsonl'
        original = raw_path.read_text()
        rows = [json.loads(x) for x in original.splitlines()]
        for name, change in (
            ('frame_join', lambda a: a[20].__setitem__('native_frame', 8000)),
            ('request_identity', lambda a: a[20].__setitem__('requested_x_m', 900)),
            ('turn_direction', lambda a: a[310].__setitem__('ego_xy_m', [90, 0])),
            ('authority_claim', lambda a: a[20].__setitem__('posted_notice_verified', True)),
            ('actor_identity', lambda a: a[20].__setitem__('actor_id', 999)),
        ):
            altered = copy.deepcopy(rows)
            change(altered)
            raw_path.write_text(''.join(json.dumps(x) + '\n' for x in altered))
            try:
                process(bundle, folder, synthetic=True)
            except (ValueError, KeyError):
                negatives.append({'case_suffix': suffix, 'mutation': name})
            else:
                raise AssertionError('Accepted altered source: ' + name)
        raw_path.write_text(original)
        missing = folder / 'driver_reference.mkv'
        missing.rename(folder / 'driver_reference.missing')
        try:
            process(bundle, folder, synthetic=True)
        except ValueError:
            negatives.append({'case_suffix': suffix, 'mutation': 'missing_camera'})
        else:
            raise AssertionError('Accepted missing camera')
        finally:
            (folder / 'driver_reference.missing').rename(missing)
        try:
            process(bundle, folder, synthetic=False)
        except ValueError:
            negatives.append({'case_suffix': suffix, 'mutation': 'synthetic_as_original'})
        else:
            raise AssertionError('Accepted synthetic source as original')
    left, right = [record['measurement'] for record in records]
    if not (left['measured_first_turn'] == 'right' and
            right['measured_first_turn'] == 'straight' and
            left['first_intersection_approach_frame'] == right['first_intersection_approach_frame'] == 299):
        raise AssertionError('First-intersection controlled contrast absent')
    receipt = {'format': 'c110875-retained-saved-taxi-source-v1',
               'frames_per_case': FRAMES, 'rate_hz': RATE,
               'records': records, 'negatives': negatives,
               'positive_count': len(records), 'negative_count': len(negatives),
               'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
               'passed': len(records) == 2 and len(negatives) == 14}
    path = HERE / 'saved-source-proof.json'
    put(path, receipt)
    print(json.dumps({'passed': receipt['passed'], 'receipt_sha256': sha(path),
                      'positives': len(records), 'negatives': len(negatives)}))


if __name__ == '__main__':
    main()
