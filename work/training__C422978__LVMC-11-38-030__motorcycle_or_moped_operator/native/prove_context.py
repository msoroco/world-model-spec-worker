"""Synthetic source-bound city/sidewalk/driveway geometry CPU proof."""
import hashlib
import json
from pathlib import Path

from measure_context import measure

HERE = Path(__file__).resolve().parent
CASES = ('witness_1', 'witness_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def rectangle(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def rejected(attempt, packet, expected, case, kind):
    path = HERE / 'context-fixtures' / 'negative' / case / (kind + '.json')
    write(path, packet)
    try:
        measure(attempt, path)
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError('Wrong context rejection: ' + str(exc)) from exc
        return {'expected': expected, 'rejected': True,
                'packet_sha256': sha(path)}
    raise AssertionError('Invalid spatial context accepted')


def prove():
    positives, negatives, driveway_controls = [], [], []
    for case in CASES:
        for candidate in CANDIDATES:
            attempt = HERE / 'saved-fixtures' / case / candidate
            packet = {'format': 'c422978-spatial-context-v1',
                      'law_id': 'LVMC-11-38-030',
                      'authority_kind': 'synthetic_cpu',
                      'city_authority_reviewed': False,
                      'map_readback_sha256': sha(attempt / 'native-map-readback.json'),
                      'native_to_context_affine': [[1, 0, 0], [0, 1, 0]],
                      'city_boundary_polygon': rectangle(-1, 0, 141, 7),
                      'sidewalk_polygon': rectangle(0, 3.5, 140, 5.5),
                      'driveway_crossing_polygons': []}
            context = HERE / 'context-fixtures' / case / candidate / 'city-context.json'
            write(context, packet)
            value = measure(attempt, context)
            assert value['frames'] == 480 and value['source_kind'] == 'synthetic_cpu'
            assert bool(value['moving_sidewalk_intersection_frames']) == (case == 'witness_2')
            assert value['moving_driveway_crossing_intersection_frames'] == 0
            assert not value['city_authority_reviewed'] and value['legal_verdict'] is None
            output = context.with_name('context-measurement.json')
            write(output, value)
            positives.append({'case_suffix': case, 'candidate_id': candidate,
                              'context_sha256': sha(context), 'measurement_sha256': sha(output),
                              'candidate_frames': value['candidate_city_sidewalk_non_driveway_frames']})
            if candidate == 'primary':
                tampered = dict(packet, map_readback_sha256='0'*64)
                negatives.append({'case_suffix': case, 'kind': 'map_hash',
                                  **rejected(attempt, tampered, 'Spatial context map readback hash differs', case, 'map_hash')})
                tampered = dict(packet, city_authority_reviewed=True)
                negatives.append({'case_suffix': case, 'kind': 'false_city_authority',
                                  **rejected(attempt, tampered, 'City authority review cannot be claimed', case, 'false_city_authority')})
                tampered = dict(packet, native_to_context_affine=[[1, 0, 0], [2, 0, 0]])
                negatives.append({'case_suffix': case, 'kind': 'singular_transform',
                                  **rejected(attempt, tampered, 'Native-to-context affine transform singular', case, 'singular_transform')})
                with_driveway = dict(packet, driveway_crossing_polygons=[rectangle(50, 3, 60, 6)])
                driveway_path = context.with_name('driveway-control.json')
                write(driveway_path, with_driveway)
                control = measure(attempt, driveway_path)
                if case == 'witness_2' and control['moving_driveway_crossing_intersection_frames'] == 0:
                    raise AssertionError('Driveway geometry did not change measured frames')
                driveway_controls.append({'case_suffix': case, 'packet_sha256': sha(driveway_path),
                                          'driveway_frames': control['moving_driveway_crossing_intersection_frames'],
                                          'candidate_non_driveway_frames': control['candidate_city_sidewalk_non_driveway_frames']})
            print(case, candidate, 'context geometry passed', flush=True)
    proof = {'format': 'c422978-synthetic-spatial-context-proof-v1',
             'processor_sha256': sha(HERE / 'measure_context.py'),
             'positives': positives, 'negatives': negatives,
             'driveway_controls': driveway_controls,
             'city_authority_or_legal_outcome_claimed': False}
    write(HERE / 'context-proof.json', proof)
    return proof


if __name__ == '__main__':
    print(json.dumps({'positives': len(prove()['positives'])}))
