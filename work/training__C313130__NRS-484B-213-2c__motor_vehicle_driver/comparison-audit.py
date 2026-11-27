"""Independent two-case tunnel contrast audit from saved CPU receipts."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ('probe_1', 'probe_2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(swap=False):
    proofs = {}
    for name in NAMES:
        folder = HERE / 'fixture-source' / name
        receipt = HERE / 'selected-proofs' / (name + '-primary-compatibility.json')
        data = json.loads(receipt.read_text())
        value = data['measurement_examples']['tunnel_approach']['value']
        proofs[name] = {'receipt_sha256': sha(receipt), 'value': value,
            'context_sha256': {source: sha(folder / source) for source in
                ('portal-geometry.json', 'road-direction-survey.json', 'centreline-geometry.json')},
            'rows': [json.loads(line) for line in (folder / 'tunnel-rows.jsonl').read_text().splitlines()]}
    first, second = (proofs[name] for name in NAMES)
    if swap:
        second['value'] = first['value']
    if first['context_sha256'] != second['context_sha256']:
        raise ValueError('Fixed tunnel context differs')
    if any(len(item['rows']) != 600 for item in (first, second)):
        raise ValueError('Incomplete 600-frame comparison')
    left1 = first['value']['left_and_blocked_within_zone_frames']
    left2 = second['value']['left_and_blocked_within_zone_frames']
    if ((first['value']['within_100_ft_driving_frames'],
            second['value']['within_100_ft_driving_frames'],
            first['value']['blocked_sight_within_zone_frames'],
            second['value']['blocked_sight_within_zone_frames']) != (153, 153, 153, 153) or
            (left1, left2) != (0, 153)):
        raise ValueError('Controlled lateral contrast absent')
    return {'comparison_id': 'training__C313130__NRS-484B-213-2c__motor_vehicle_driver__comparison',
        'cases': [item['case_id'] for item in json.loads((HERE / 'execution-manifest.json').read_text())['cases']],
        'context_sha256': first['context_sha256'], 'left_and_blocked_frames': [left1, left2],
        'cpu_diagnostic_only': True, 'original_native_observed': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative-swap', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.negative_swap), sort_keys=True))
