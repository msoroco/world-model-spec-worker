"""Retain synthetic trigger and nontrigger probes for each passing fallback."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from triggers import evaluate

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, data):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in data))


def rejected(call):
    try:
        call()
    except (ValueError, TypeError):
        return True
    raise AssertionError('Mutated passing trigger source accepted')


def prove():
    fixtures = []
    for distance in (70, 120, 170):
        folder = HERE/'saved-fixtures'/str(distance)
        expected = {'native-observed.jsonl': sha(folder/'native-observed.jsonl'),
                    'road-readback.json': sha(folder/'road-readback.json')}
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            receipt = evaluate(distance, candidate, folder, expected)
            expected_decision = (distance == 70 if candidate == 'fallback1'
                                 else distance in (70, 120) if candidate == 'fallback2'
                                 else False)
            if receipt['triggered'] is not expected_decision:
                raise AssertionError('Measured fallback decision differs')
            fixtures.append({'distance_m': distance, 'candidate_id': candidate,
                             'source_hashes': expected, 'triggered': receipt['triggered'],
                             'metric': receipt['metric']})
    with tempfile.TemporaryDirectory(dir=HERE) as temporary:
        folder = Path(temporary)
        source = HERE/'saved-fixtures'/'170'
        shutil.copy2(source/'road-readback.json', folder/'road-readback.json')
        original = rows(source/'native-observed.jsonl')
        altered = json.loads(json.dumps(original))
        altered[60]['sightline_visible'] = False
        write_rows(folder/'native-observed.jsonl', altered)
        visibility_receipt = evaluate(170, 'fallback3', folder)
        if visibility_receipt['triggered'] is not True:
            raise AssertionError('Occluded left phase did not route to abort fallback')
        retained = HERE/'trigger-fixtures'/'occluded-170'
        retained.mkdir(parents=True, exist_ok=True)
        shutil.copy2(folder/'road-readback.json', retained/'road-readback.json')
        shutil.copy2(folder/'native-observed.jsonl', retained/'native-observed.jsonl')
        negatives = [
            {'mutation': 'incorrect_saved_source_hash',
             'rejected': rejected(lambda: evaluate(170, 'fallback3', folder,
                                                  {'native-observed.jsonl': '0'*64,
                                                   'road-readback.json': sha(folder/'road-readback.json')}))},
        ]
        altered[60].pop('sightline_visible')
        write_rows(folder/'native-observed.jsonl', altered)
        negatives.append({'mutation': 'missing_sightline_observation',
                          'rejected': rejected(lambda: evaluate(170, 'fallback3', folder))})
        write_rows(folder/'native-observed.jsonl', original)
        road = json.loads((folder/'road-readback.json').read_text())
        road['travel_directions'] = 1
        (folder/'road-readback.json').write_text(json.dumps(road)+'\n')
        negatives.append({'mutation': 'one_direction_road',
                          'rejected': rejected(lambda: evaluate(170, 'fallback2', folder))})
    proof = {'format': 'c102951-saved-trigger-proof-v1',
             'assignment_id': HERE.parent.name,
             'construction_manifest_sha256': sha(HERE/'drafts/manifest.json'),
             'trigger_code_sha256': sha(HERE/'triggers.py'),
             'saved_processor_sha256': sha(HERE/'measure_pass.py'),
             'fixtures': fixtures,
             'visibility_trigger': {'distance_m': 170, 'candidate_id': 'fallback3',
                                    'source_kind': 'synthetic_cpu',
                                    'changed_frame': 60, 'triggered': True,
                                    'source_hashes': {
                                        'native-observed.jsonl': sha(retained/'native-observed.jsonl'),
                                        'road-readback.json': sha(retained/'road-readback.json')}},
             'negative_controls': negatives,
             'original_native_observed': False,
             'safe_distance_judgment': None, 'legal_verdict': None,
             'delivery_ready': False}
    (HERE/'trigger-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    result = prove()
    print(json.dumps({'fixtures': len(result['fixtures']),
                      'visibility_trigger': result['visibility_trigger']['triggered'],
                      'negative_controls': len(result['negative_controls'])}))
