"""Independent raw-row audit of synthetic spatial context proof."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('witness_1', 'witness_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def touches(box, bounds):
    x0, y0, x1, y1 = box
    a, b, c, d = bounds
    return x0 <= c and x1 >= a and y0 <= d and y1 >= b


def box(row):
    points = row['body_native_xy_m']
    assert len(points) == 4
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def audit():
    proof = read(HERE / 'context-proof.json')
    assert proof['format'] == 'c422978-synthetic-spatial-context-proof-v1'
    assert proof['processor_sha256'] == sha(HERE / 'measure_context.py')
    assert proof['city_authority_or_legal_outcome_claimed'] is False
    assert len(proof['positives']) == 8 and len(proof['negatives']) == 6
    assert len(proof['driveway_controls']) == 2
    expected_pairs = {(case, candidate) for case in CASES for candidate in CANDIDATES}
    assert {(p['case_suffix'], p['candidate_id']) for p in proof['positives']} == expected_pairs
    audited = []
    for item in proof['positives']:
        case, candidate = item['case_suffix'], item['candidate_id']
        attempt = HERE / 'saved-fixtures' / case / candidate
        fixture = HERE / 'context-fixtures' / case / candidate
        context_path = fixture / 'city-context.json'
        measurement_path = fixture / 'context-measurement.json'
        context, value = read(context_path), read(measurement_path)
        assert item['context_sha256'] == sha(context_path)
        assert item['measurement_sha256'] == sha(measurement_path)
        assert context['authority_kind'] == 'synthetic_cpu'
        assert context['city_authority_reviewed'] is False
        assert context['native_to_context_affine'] == [[1, 0, 0], [0, 1, 0]]
        assert context['sidewalk_polygon'] == [[0, 3.5], [140, 3.5], [140, 5.5], [0, 5.5]]
        assert context['city_boundary_polygon'] == [[-1, 0], [141, 0], [141, 7], [-1, 7]]
        assert context['driveway_crossing_polygons'] == []
        assert context['map_readback_sha256'] == sha(attempt / 'native-map-readback.json')
        observed_path = attempt / 'native-observed.jsonl'
        rows = [json.loads(line) for line in observed_path.read_text().splitlines()]
        assert len(rows) == 480
        assert all(row['frame'] == i and row['source_kind'] == 'synthetic_cpu'
                   and row['motorcycle_blueprint'] == 'vehicle.kawasaki.ninja'
                   for i, row in enumerate(rows))
        moving = [box(row) for row in rows if row['speed_mps'] > .1]
        sidewalk = sum(touches(b, (0, 3.5, 140, 5.5)) for b in moving)
        city = sum(touches(b, (-1, 0, 141, 7)) for b in moving)
        assert value['frames'] == 480 and value['source_kind'] == 'synthetic_cpu'
        assert value['moving_sidewalk_intersection_frames'] == sidewalk
        assert value['moving_city_boundary_intersection_frames'] == city
        assert value['moving_driveway_crossing_intersection_frames'] == 0
        assert value['candidate_city_sidewalk_non_driveway_frames'] == sidewalk == item['candidate_frames']
        assert value['city_authority_reviewed'] is False
        assert value['driveway_rule_composition_reviewed'] is False
        assert value['legal_verdict'] is None
        assert value['source_hashes'] == {
            'native-observed.jsonl': sha(observed_path),
            'native-map-readback.json': sha(attempt / 'native-map-readback.json'),
            'city-context.json': sha(context_path)}
        audited.append((case, candidate, sidewalk))
    expectations = {'map_hash': 'Spatial context map readback hash differs',
                    'false_city_authority': 'City authority review cannot be claimed',
                    'singular_transform': 'Native-to-context affine transform singular'}
    for item in proof['negatives']:
        case, kind = item['case_suffix'], item['kind']
        assert case in CASES and kind in expectations
        path = HERE / 'context-fixtures' / 'negative' / case / (kind + '.json')
        packet = read(path)
        assert sha(path) == item['packet_sha256']
        assert item['rejected'] is True and item['expected'] == expectations[kind]
        valid = read(HERE / 'context-fixtures' / case / 'primary' / 'city-context.json')
        changes = {k for k in valid if packet.get(k) != valid[k]}
        assert changes == {'map_readback_sha256' if kind == 'map_hash' else
                           'city_authority_reviewed' if kind == 'false_city_authority' else
                           'native_to_context_affine'}
        if kind == 'map_hash':
            assert packet['map_readback_sha256'] != valid['map_readback_sha256']
        elif kind == 'false_city_authority':
            assert packet['city_authority_reviewed'] is True
        else:
            a, b = packet['native_to_context_affine']
            assert a[0]*b[1] - a[1]*b[0] == 0
    for item in proof['driveway_controls']:
        case = item['case_suffix']
        assert case in CASES
        fixture = HERE / 'context-fixtures' / case / 'primary'
        path = fixture / 'driveway-control.json'
        packet = read(path)
        assert sha(path) == item['packet_sha256']
        expected = read(fixture / 'city-context.json')
        assert {k for k in packet if packet[k] != expected[k]} == {'driveway_crossing_polygons'}
        assert packet['driveway_crossing_polygons'] == [[[50, 3], [60, 3], [60, 6], [50, 6]]]
        attempt = HERE / 'saved-fixtures' / case / 'primary'
        rows = [json.loads(line) for line in (attempt / 'native-observed.jsonl').read_text().splitlines()]
        moving = [box(row) for row in rows if row['speed_mps'] > .1]
        driveway = sum(touches(b, (50, 3, 60, 6)) for b in moving)
        non_driveway = sum(touches(b, (0, 3.5, 140, 5.5)) and
                           not touches(b, (50, 3, 60, 6)) for b in moving)
        assert item['driveway_frames'] == driveway
        assert item['candidate_non_driveway_frames'] == non_driveway
        assert driveway > 0 if case == 'witness_2' else driveway == 0
    result = {'format': 'c422978-independent-context-audit-v1',
              'proof_sha256': sha(HERE / 'context-proof.json'),
              'audited': [{'case_suffix': case, 'candidate_id': candidate,
                           'moving_sidewalk_intersection_frames': count}
                          for case, candidate, count in audited],
              'negative_packets_verified': 6, 'driveway_controls_verified': 2,
              'city_authority_or_legal_outcome_claimed': False}
    path = HERE / 'context-audit.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
