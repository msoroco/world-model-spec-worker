"""Audit C125745 comparison measurements in retained compatibility receipts.

This is software source integrity only. Full delivery audit requires accepted
Native recordings with all planned frames and original camera pixels.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = {
    'stop_sign_relative_side': ('stop_ego_left_near_time', 'stop_ego_right_near_time'),
    'stop_sign_entry_timing': ('stop_ego_left_near_time', 'stop_ego_left_separated'),
}


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest = read(HERE / 'execution-manifest.json')
    plan = read(HERE / 'case-plan.json')
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    declared = {row['comparison_id']: row for row in plan['comparisons']}
    require(set(declared) == set(EXPECTED), 'Exact declared comparison set required')
    receipts = {}
    for key, suffixes in EXPECTED.items():
        case_ids = [HERE.name + '__' + suffix for suffix in suffixes]
        require(declared[key]['case_ids'] == case_ids, 'Exact comparison case order required')
        for case_id in case_ids:
            entry = entries[case_id]
            path = HERE / entry['compatibility']['receipt']
            require(sha(path) == entry['compatibility']['sha256'], 'Compatibility receipt hash changed')
            receipt = read(path)
            require(receipt['passed'] and receipt['case_id'] == case_id and
                    receipt['construction_sha256'] == entry['construction_sha256'],
                    'Exact source-bound compatibility proof required')
            require(receipt['negative_removed'] == 'controller_history.jsonl' and
                    receipt['negative_error_contains'] ==
                    'Missing required source: controller_history.jsonl',
                    'Negative controller-source rejection required')
            examples = receipt['measurement_examples']
            require({'crossing_identity', 'device_qualification_context',
                     'entry_timing', 'relative_right_side'} <= set(examples),
                    'Missing source-specific comparison measurement')
            require(all(row['sources'] for row in examples.values()),
                    'Every measurement needs original source hashes')
            receipts[case_id] = receipt
    pairs = []
    for key, suffixes in EXPECTED.items():
        a, b = [receipts[HERE.name + '__' + suffix] for suffix in suffixes]
        av, bv = a['measurement_examples'], b['measurement_examples']
        ac, bc = av['crossing_identity']['value'], bv['crossing_identity']['value']
        require((ac['native_map_id'], ac['intersection_id'], ac['ego_highway_id'],
                 ac['other_highway_id']) ==
                (bc['native_map_id'], bc['intersection_id'], bc['ego_highway_id'],
                 bc['other_highway_id']), 'Comparison crossing or highway identity changed')
        require(av['device_qualification_context']['value']['native_stop_sign_id'] ==
                bv['device_qualification_context']['value']['native_stop_sign_id'],
                'Governing stop sign changed')
        at = av['entry_timing']['value']['absolute_difference_s']
        bt = bv['entry_timing']['value']['absolute_difference_s']
        ar = av['relative_right_side']['value']['other_spatially_right']
        br = bv['relative_right_side']['value']['other_spatially_right']
        if key == 'stop_sign_relative_side':
            require(ar is True and br is False and abs(at - bt) < 1e-9,
                    'Relative-side difference or fixed entry timing missing')
        else:
            require(ar is True and br is True and at < bt,
                    'Fixed side or separated measured timing missing')
        pairs.append({'comparison_id': key, 'case_ids': declared[key]['case_ids'],
                      'entry_time_differences_s': [at, bt],
                      'other_spatially_right': [ar, br]})
    return {'format': 'worker-c125745-compatibility-comparison-audit',
            'software_comparisons_passed': True, 'comparisons': pairs,
            'scope': 'retained synthetic original-source compatibility receipts',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
