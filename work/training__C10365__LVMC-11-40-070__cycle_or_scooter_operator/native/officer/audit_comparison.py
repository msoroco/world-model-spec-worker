"""Independent diagnostic comparison of device obedience and officer exception."""
import hashlib
import json
from pathlib import Path
import tempfile

from build import HERE
from prove_saved import fixture
from saved import process, read_rows

ROOT = HERE.parents[3]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(a, b):
    bundle_a, raw_a, video_a, review_a = a
    bundle_b, raw_b, video_b, review_b = b
    ca = json.loads((bundle_a / 'config.json').read_text())
    cb = json.loads((bundle_b / 'config.json').read_text())
    if not ca['case_id'].endswith('__probe_a') or not cb['case_id'].endswith('__probe_b'):
        raise ValueError('Exact controlled pair differs')
    fixed = ('assignment_id', 'assignment_sha256', 'source_text', 'rate_hz', 'frames',
             'rider_blueprint', 'camera_sources', 'camera_policy', 'road_sha256',
             'device_id', 'device_station_x_m', 'officer_position_xy_m',
             'officer_blueprint_filter')
    for key in fixed:
        if key not in ca or key not in cb or ca[key] != cb[key]:
            raise ValueError('Fixed configuration differs: ' + key)
    ra, rb = read_rows(raw_a), read_rows(raw_b)
    va, vb = read_rows(video_a), read_rows(video_b)
    if len(ra) != 600 or len(rb) != 600 or va != vb:
        raise ValueError('Matched 600-frame video mapping differs')
    for left, right in zip(ra, rb):
        for key in ('observed_road_id', 'observed_lane_id', 'source_kind'):
            if left.get(key) != right.get(key):
                raise ValueError('Fixed native source differs: ' + key)
        for actor in ('rider', 'officer_actor'):
            for key in ('actor_id', 'blueprint'):
                if left[actor][key] != right[actor][key]:
                    raise ValueError('Fixed participant identity differs')
        if left['officer_actor']['center_native_xyz_m'] != right['officer_actor']['center_native_xyz_m']:
            raise ValueError('Fixed officer staging differs')
    review_left, review_right = json.loads(review_a.read_text()), json.loads(review_b.read_text())
    for key in ('source_kind', 'device_id', 'device_applicable', 'rider_class', 'officer_actor_id'):
        if review_left.get(key) != review_right.get(key):
            raise ValueError('Fixed reviewed context differs: ' + key)
    pa, pb = process(bundle_a, raw_a, video_a, review_a, synthetic=True), \
             process(bundle_b, raw_b, video_b, review_b, synthetic=True)
    if pa['stopped'] is not True or pa['crossing_frame'] is not None or \
            pa['officer_direction_reviewed'] != 'none_contrary':
        raise ValueError('Device-obedience source contrast differs')
    if pb['crossing_frame'] is None or pb['officer_direction_reviewed'] != 'proceed':
        raise ValueError('Officer-exception source contrast differs')
    return {'format': 'c10365-source-comparison-audit-v1', 'passed': True,
            'case_ids': [ca['case_id'], cb['case_id']], 'frames_per_case': 600,
            'fixed_config_fields': list(fixed),
            'measured': {'device_obedience_stopped': pa['stopped'],
                         'device_obedience_crossed': pa['crossing_frame'] is not None,
                         'officer_exception_crossed': pb['crossing_frame'] is not None,
                         'reviewed_directions': [pa['officer_direction_reviewed'],
                                                 pb['officer_direction_reviewed']]},
            'source_hashes': {'probe_a': {name: sha(path) for name, path in
                               (('raw', raw_a), ('video', video_a), ('review', review_a))},
                              'probe_b': {name: sha(path) for name, path in
                               (('raw', raw_b), ('video', video_b), ('review', review_b))}},
            'original_native_observed': False, 'physical_legal_verdict': None}


def reject(a, b, path, mutate, expected):
    original = path.read_text()
    try:
        mutate(path)
        try:
            audit(a, b)
        except ValueError as exc:
            if expected not in str(exc):
                raise AssertionError(str(exc)) from exc
            return {'mutation': expected, 'error': str(exc)}
        raise AssertionError('Altered comparison accepted: ' + expected)
    finally:
        path.write_text(original)


def write_rows(path, values):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))


def run():
    (ROOT / '.runtime-work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c10365-comparison-') as temp:
        base = Path(temp)
        a_dir, b_dir = base / 'a', base / 'b'
        a_dir.mkdir()
        b_dir.mkdir()
        a_bundle = HERE / 'drafts/probe_a/primary'
        b_bundle = HERE / 'drafts/probe_b/primary'
        a = (a_bundle, *fixture(a_bundle, a_dir))
        b = (b_bundle, *fixture(b_bundle, b_dir))
        positive = audit(a, b)
        negatives = [
            reject(a, b, b[2], lambda p: write_rows(p, [dict(row, native_frame=999)
                   if i == 100 else row for i, row in enumerate(read_rows(p))]),
                   'Matched 600-frame video mapping differs'),
            reject(a, b, b[1], lambda p: write_rows(p, [dict(row, observed_lane_id=-2)
                   if i == 100 else row for i, row in enumerate(read_rows(p))]),
                   'Fixed native source differs'),
            reject(a, b, b[1], lambda p: write_rows(p, [dict(row, officer_actor=dict(
                   row['officer_actor'], center_native_xyz_m=[99, 99, 1]))
                   if i == 100 else row for i, row in enumerate(read_rows(p))]),
                   'Fixed officer staging differs'),
            reject(a, b, b[3], lambda p: p.write_text(json.dumps(dict(
                   json.loads(p.read_text()), device_id='unmatched'))),
                   'Fixed reviewed context differs'),
        ]
    receipt = {'format': 'c10365-source-comparison-proof-v1',
               'positive': positive, 'negatives': negatives,
               'original_native_observed': False, 'physical_legal_verdict': None}
    (HERE / 'source-comparison-proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return {'positives': 1, 'negatives': len(negatives)}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
