"""Exercise all fallback triggers on the runner's saved schema using synthetic rows."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from triggers import evaluate

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(rows):
    return hashlib.sha256(''.join(json.dumps(row, sort_keys=True) + '\n'
                                  for row in rows).encode()).hexdigest()


def native_rows(rows):
    converted = []
    for index, old in enumerate(rows):
        x, y = old['center_xy_m']
        converted.append({'frame': index, 'native_frame': 1000 + index,
                          'time_s': old['time_s'] + .05,
                          'source_kind': 'original_native',
                          'motorcycle_blueprint': old['motorcycle_blueprint'],
                          'center_native_xy_m': [x, -y],
                          'body_native_xy_m': [[px, -py] for px, py in old['body_xy_m']],
                          'speed_mps': old['speed_mps']})
    return converted


def rejected(case, candidate, rows, visibility, message):
    try:
        evaluate(case, candidate, rows, visibility)
    except ValueError as error:
        if str(error) != message:
            raise
        return {'rejected': True, 'error': message, 'rows_sha256': digest(rows)}
    raise AssertionError('Invalid Native-shaped trigger packet accepted')


def main():
    receipts = []
    negatives = []
    with tempfile.TemporaryDirectory(prefix='c422978-native-trigger-') as temporary:
        temp = Path(temporary)
        for case in ('witness_1', 'witness_2'):
            for candidate in ('fallback1', 'fallback2', 'fallback3'):
                for fixture in ('trigger', 'nontrigger'):
                    source = HERE / 'trigger-fixtures' / case / candidate / fixture
                    rows = native_rows([json.loads(line) for line in
                                        (source / 'actor-frames.jsonl').read_text().splitlines()])
                    visibility = None
                    if candidate == 'fallback3':
                        video = temp / 'synthetic-camera.txt'
                        video.write_bytes((source / 'synthetic-camera.txt').read_bytes())
                        visibility = temp / 'visibility.json'
                        packet = json.loads((source / 'visibility.json').read_text())
                        packet['source_kind'] = 'original_native'
                        visibility.write_text(json.dumps(packet) + '\n')
                    result = evaluate(case, candidate, rows, visibility)
                    if result['triggered'] != (fixture == 'trigger') or result['source_kind'] != 'original_native':
                        raise AssertionError('Native-shaped fallback trigger split differs')
                    receipts.append({'case_suffix': case, 'candidate_id': candidate,
                                     'fixture': fixture,
                                     'source_sha256': sha(source / 'actor-frames.jsonl'),
                                     'native_rows_sha256': digest(rows), 'result': result})
                    if case == 'witness_2' and candidate == 'fallback1' and fixture == 'trigger':
                        bad = copy.deepcopy(rows)
                        bad[17]['source_kind'] = 'native_original'
                        negatives.append({'kind': 'mixed_provenance', **rejected(case, candidate, bad, None,
                                          'Saved source provenance absent')})
                        bad = copy.deepcopy(rows)
                        bad[17]['native_frame'] += 1
                        negatives.append({'kind': 'native_frame_join', **rejected(case, candidate, bad, None,
                                          'Saved Native frame sequence differs')})
                        bad = copy.deepcopy(rows)
                        bad[17]['time_s'] += .02
                        negatives.append({'kind': 'timestamp_join', **rejected(case, candidate, bad, None,
                                          'Saved motorcycle identity or time differs')})
                    if case == 'witness_2' and candidate == 'fallback3' and fixture == 'trigger':
                        packet['source_kind'] = 'synthetic_cpu'
                        visibility.write_text(json.dumps(packet) + '\n')
                        negatives.append({'kind': 'camera_provenance', **rejected(case, candidate, rows, visibility,
                                          'Camera review provenance differs')})
                        packet['source_kind'] = 'original_native'
                        packet['video_sha256'] = '0' * 64
                        visibility.write_text(json.dumps(packet) + '\n')
                        negatives.append({'kind': 'camera_source_hash', **rejected(case, candidate, rows, visibility,
                                          'Camera source hash differs')})
    proof = {'format': 'c422978-native-schema-trigger-proof-v1',
             'scope': 'Synthetic source rows converted to the exact original_native runner schema and 50 ms first capture time; no original capture claimed',
             'trigger_code_sha256': sha(HERE / 'triggers.py'),
             'receipts': receipts, 'negatives': negatives,
             'original_native_observed': False, 'delivery_ready': False}
    (HERE / 'native-trigger-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'positives': len(receipts), 'negatives': len(negatives)}))


if __name__ == '__main__':
    main()
