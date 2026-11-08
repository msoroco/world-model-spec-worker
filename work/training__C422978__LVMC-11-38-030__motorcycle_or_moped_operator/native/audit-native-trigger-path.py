"""Recompute Native-shaped trigger results and decisive tamper hashes independently."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(rows):
    return hashlib.sha256(''.join(json.dumps(row, sort_keys=True) + '\n'
                                  for row in rows).encode()).hexdigest()


def convert(rows):
    output = []
    for index, old in enumerate(rows):
        output.append({'frame': index, 'native_frame': index + 1000,
                       'time_s': old['time_s'] + .05,
                       'source_kind': 'original_native',
                       'motorcycle_blueprint': old['motorcycle_blueprint'],
                       'center_native_xy_m': [old['center_xy_m'][0], -old['center_xy_m'][1]],
                       'body_native_xy_m': [[p[0], -p[1]] for p in old['body_xy_m']],
                       'speed_mps': old['speed_mps']})
    return output


def main():
    proof = json.loads((HERE / 'native-trigger-proof.json').read_text())
    assert proof['format'] == 'c422978-native-schema-trigger-proof-v1'
    assert proof['trigger_code_sha256'] == sha(HERE / 'triggers.py')
    assert proof['original_native_observed'] is False and proof['delivery_ready'] is False
    assert len(proof['receipts']) == 12 and len(proof['negatives']) == 5
    indexed = {}
    for receipt in proof['receipts']:
        case, candidate, fixture = (receipt[key] for key in
                                    ('case_suffix', 'candidate_id', 'fixture'))
        assert case in ('witness_1', 'witness_2')
        assert candidate in ('fallback1', 'fallback2', 'fallback3')
        assert fixture in ('trigger', 'nontrigger')
        source = HERE / 'trigger-fixtures' / case / candidate / fixture
        path = source / 'actor-frames.jsonl'
        assert receipt['source_sha256'] == sha(path)
        rows = convert([json.loads(line) for line in path.read_text().splitlines()])
        assert len(rows) == 480 and receipt['native_rows_sha256'] == digest(rows)
        assert all(row['native_frame'] == 1000+i and
                   abs(row['time_s'] - (.05+i/20)) < 1e-8 and
                   row['source_kind'] == 'original_native'
                   for i, row in enumerate(rows))
        overlaps, gaps = [], []
        for index, row in enumerate(rows):
            ys = [point[1] for point in row['body_native_xy_m']]
            if row['speed_mps'] > .1 and min(ys) < 5.5 and max(ys) > 3.5:
                overlaps.append(index)
            gaps.append(3.5-max(ys))
        if candidate == 'fallback1':
            expected = (overlaps[0] if overlaps else None) if case == 'witness_2' else len(overlaps)
        elif candidate == 'fallback2':
            expected = len(overlaps) if case == 'witness_2' else min(gaps)
        else:
            packet = json.loads((source / 'visibility.json').read_text())
            assert packet['video_sha256'] == sha(source / packet['video_path'])
            expected = packet['visible_fraction']
        result = receipt['result']
        assert result['value'] == expected
        threshold = ({'fallback1': 90, 'fallback2': 380, 'fallback3': .75}[candidate]
                     if case == 'witness_2' else
                     {'fallback1': 0, 'fallback2': 1.0, 'fallback3': .75}[candidate])
        assert result['threshold'] == threshold
        expected_triggered = ((expected is None or expected > threshold)
                              if candidate == 'fallback1' else expected < threshold)
        assert result['triggered'] == expected_triggered
        assert result['triggered'] == (fixture == 'trigger')
        assert result['source_kind'] == 'original_native'
        assert result['legal_outcome_claimed'] is False
        key = case, candidate, fixture
        assert key not in indexed
        indexed[key] = rows
    assert len(indexed) == 12
    expected_errors = {
        'mixed_provenance': 'Saved source provenance absent',
        'native_frame_join': 'Saved Native frame sequence differs',
        'timestamp_join': 'Saved motorcycle identity or time differs',
        'camera_provenance': 'Camera review provenance differs',
        'camera_source_hash': 'Camera source hash differs'}
    assert {item['kind'] for item in proof['negatives']} == set(expected_errors)
    for item in proof['negatives']:
        assert item['rejected'] is True and item['error'] == expected_errors[item['kind']]
        if item['kind'] in ('mixed_provenance', 'native_frame_join', 'timestamp_join'):
            rows = json.loads(json.dumps(indexed['witness_2', 'fallback1', 'trigger']))
            if item['kind'] == 'mixed_provenance': rows[17]['source_kind'] = 'native_original'
            elif item['kind'] == 'native_frame_join': rows[17]['native_frame'] += 1
            else: rows[17]['time_s'] += .02
        else:
            rows = indexed['witness_2', 'fallback3', 'trigger']
        assert item['rows_sha256'] == digest(rows)
    result = {'format': 'c422978-independent-native-trigger-audit-v1',
              'proof_sha256': sha(HERE / 'native-trigger-proof.json'),
              'positive_rows_audited': 12, 'negative_cases_audited': 5,
              'original_native_observed': False, 'delivery_ready': False}
    (HERE / 'native-trigger-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
