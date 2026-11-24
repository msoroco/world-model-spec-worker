"""Retained 600-frame source-pair checks across target-preserving candidates.

Synthetic diagnostic only. This does not establish original Native behavior.
"""
from pathlib import Path
import hashlib
import json

from prove_saved import fixture
from saved import process

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / '.runtime-work/c109137-current-candidate-sources'
ASSIGNMENT = 'training__C109137__NRS-484B-217-2__motor_vehicle_driver'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def independent_source_events(raw, video):
    source, mapping = rows(raw), rows(video)
    if len(source) != 600 or len(mapping) != 600:
        raise ValueError('Independent full 600-frame source window absent')
    first_stripe = first_adjoining = first_signal = None
    for index, (actor, frame) in enumerate(zip(source, mapping)):
        if actor['frame'] != index or frame['video_frame'] != index \
                or actor['native_frame'] != frame['native_frame'] \
                or abs(actor['time_s'] - frame['time_s']) > 1e-6:
            raise ValueError('Independent source/video join differs')
        if actor['ego']['light_state'] == 32 and first_signal is None:
            first_signal = index
        body = actor['ego']['body_native_xyz_m']
        if len(body) != 8:
            raise ValueError('Independent original body absent')
        lower = min(v[1] for v in body)
        upper = max(v[1] for v in body)
        if lower <= 0 <= upper and first_stripe is None:
            first_stripe = index
        if actor['observed_road_id'] == 218 and first_adjoining is None:
            first_adjoining = index
    return {'first_stripe_body_frame': first_stripe,
            'first_adjoining_road_frame': first_adjoining,
            'first_left_indicator_frame': first_signal}


def verify_hashes(paths, expected):
    for path in paths:
        if not path.is_file() or sha(path) != expected[path.name]:
            raise ValueError('Retained source hash differs: ' + path.name)


def main():
    manifest = json.loads((HERE / 'current-primary-intent-manifest.json').read_text())
    constructions = {'primary': manifest['cases'][0]['construction_sha256']}
    constructions.update({x['id']: x['construction_sha256']
                          for x in manifest['cases'][0]['candidates']})
    records = []
    negatives = []
    for candidate in ('primary', 'fallback1', 'fallback2'):
        pair = []
        for suffix in ('probe_1', 'probe_2'):
            bundle = HERE / 'drafts' / suffix / candidate
            raw, video, review = fixture(bundle, OUT / suffix / candidate)
            measured = process(bundle, raw, video, review, synthetic=True)
            events = independent_source_events(raw, video)
            if measured['first_observed_stripe_frame'] != events['first_stripe_body_frame']:
                raise AssertionError('Independent crossing differs from saved measurement')
            if measured['first_adjoining_lane_frame'] != events['first_adjoining_road_frame']:
                raise AssertionError('Independent adjoining-road entry differs')
            if measured['first_observed_signal_frame'] != events['first_left_indicator_frame']:
                raise AssertionError('Independent indicator differs')
            if measured['delivery_ready'] or measured['physical_legal_verdict'] is not None:
                raise AssertionError('Synthetic source claimed physical or legal acceptance')
            hashes = {x.name: sha(x) for x in (raw, video, review)}
            verify_hashes((raw, video, review), hashes)
            original = raw.read_bytes()
            try:
                with raw.open('ab') as stream:
                    stream.write(b'{}\n')
                try:
                    verify_hashes((raw, video, review), hashes)
                except ValueError as exc:
                    negatives.append({'case_id': ASSIGNMENT + '__' + suffix,
                                      'candidate_id': candidate, 'mutation': 'changed_raw_bytes',
                                      'rejection': str(exc)})
                else:
                    raise AssertionError('Changed retained source accepted')
            finally:
                raw.write_bytes(original)
            pair.append({'case_id': ASSIGNMENT + '__' + suffix,
                         'candidate_id': candidate,
                         'current_construction_sha256': (
                             constructions[candidate] if suffix == 'probe_1' else
                             sha(HERE / 'runtime-drafts' / suffix / candidate / 'construction.json')),
                         'source_sha256': hashes,
                         'measurement': measured,
                         'independent_events': events})
        a, b = pair
        fixed = ('first_stripe_body_frame', 'first_adjoining_road_frame')
        if any(a['independent_events'][k] != b['independent_events'][k] for k in fixed):
            raise AssertionError('Target-preserving pair changed crossing geometry')
        if a['independent_events']['first_left_indicator_frame'] is None \
                or b['independent_events']['first_left_indicator_frame'] is not None:
            raise AssertionError('Controlled prior-indicator difference absent')
        records.extend(pair)
    report = {'format': 'c109137-current-candidate-source-pairs-v1',
              'source_kind': 'synthetic_fixture', 'rate_hz': 20, 'frames': 600,
              'candidate_pairs': 3, 'records': records,
              'negative_rejections': negatives,
              'current_manifest_sha256': sha(HERE / 'current-primary-intent-manifest.json'),
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
              'passed': True}
    path = HERE / 'current-candidate-pairs-proof.json'
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': True, 'pairs': 3, 'source_windows': len(records),
                      'negative_rejections': len(negatives),
                      'receipt_sha256': sha(path)}))


if __name__ == '__main__':
    main()
