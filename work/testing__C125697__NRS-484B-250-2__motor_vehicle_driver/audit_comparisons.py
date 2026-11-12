"""Independent CPU audit of C125697's four declared case comparisons."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = {'relative_right_side', 'entry_timing', 'device_qualification',
            'opposite_left_turn_exception_context'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load_case(entry, root=HERE):
    case = entry['case_id']
    construction = root / entry['construction']
    require(construction.is_file() and sha(construction) == entry['construction_sha256'],
            'Missing or changed construction: ' + case)
    bundle = json.loads(construction.read_text())
    config = json.loads(next(item['content'] for item in bundle['files']
                             if item['path'] == 'config.json'))
    receipt_info = entry.get('compatibility') or {}
    receipt_file = root / receipt_info.get('receipt', '__missing__')
    require(receipt_file.is_file() and sha(receipt_file) == receipt_info.get('sha256'),
            'Missing or changed source proof: ' + case)
    receipt = json.loads(receipt_file.read_text())
    require(receipt.get('passed') is True and receipt.get('case_id') == case and
            receipt.get('candidate_id') == 'primary' and
            receipt.get('construction_sha256') == entry['construction_sha256'] and
            receipt.get('negative_removed') == 'crossing_history.jsonl',
            'Invalid positive/negative source proof: ' + case)
    measured = receipt.get('measurement_examples')
    require(isinstance(measured, dict) and all(
        key in measured for key in ('crossing_identity', 'entry_timing',
                                    'relative_right_side', 'device_qualification_context',
                                    'opposite_left_turn_context')),
            'Missing original-source measurements: ' + case)
    return {'config': config, 'measured': {k: v['value'] for k, v in measured.items()},
            'construction_sha256': entry['construction_sha256'],
            'compatibility_sha256': sha(receipt_file)}


def audit_pair(name, left, right):
    a, b = left['config'], right['config']
    av, bv = left['measured'], right['measured']
    common = ('native_map_name', 'crossing_id', 'crossing_polygon_xy_m',
              'same_statutory_crossing')
    require(all(a['site'][key] == b['site'][key] for key in common) and
            a['actor'] == b['actor'] and a['rate_hz'] == b['rate_hz'] == 20 and
            a['duration_s'] == b['duration_s'] == 45,
            name + ': fixed crossing, actor or source capture differs')
    require(av['crossing_identity']['intersection_id'] ==
            bv['crossing_identity']['intersection_id'],
            name + ': measured crossing identity differs')
    if name == 'relative_right_side':
        require(set((a['site']['ego_highway_id'], a['site']['other_highway_id'])) ==
                set((b['site']['ego_highway_id'], b['site']['other_highway_id'])),
                name + ': highway identities differ')
        require(a['other_approach_side'] == 'right' and
                b['other_approach_side'] == 'left' and
                av['relative_right_side']['other_spatially_right_of_ego_approach'] is True and
                bv['relative_right_side']['other_spatially_right_of_ego_approach'] is False and
                av['entry_timing']['absolute_difference_s'] ==
                bv['entry_timing']['absolute_difference_s'],
                name + ': side or fixed entry timing not demonstrated')
    elif name == 'entry_timing':
        require(a['site']['routes'] == b['site']['routes'] and
                a['site']['ego_highway_id'] == b['site']['ego_highway_id'] and
                a['site']['other_highway_id'] == b['site']['other_highway_id'] and
                a['other_approach_side'] == b['other_approach_side'] and
                av['device_qualification_context']['all_sampled_states_off'] and
                bv['device_qualification_context']['all_sampled_states_off'] and
                av['entry_timing']['absolute_difference_s'] <
                bv['entry_timing']['absolute_difference_s'],
                name + ': fixed approach or measured timing difference missing')
    elif name == 'device_qualification':
        require(a['site']['routes'] == b['site']['routes'] and
                a['site']['entrance_road_lanes'] == b['site']['entrance_road_lanes'] and
                av['device_qualification_context']['all_sampled_states_off'] and
                bv['device_qualification_context']['all_sampled_states_operative'] and
                (bv['device_qualification_context']['ego_governing_state'],
                 bv['device_qualification_context']['other_governing_state']) ==
                ('Red', 'Green') and
                av['entry_timing']['absolute_difference_s'] ==
                bv['entry_timing']['absolute_difference_s'],
                name + ': fixed routes or operative head difference missing')
    elif name == 'opposite_left_turn_exception_context':
        turn = bv['opposite_left_turn_context']
        require(a['site']['ego_highway_id'] != a['site']['other_highway_id'] and
                b['site']['ego_highway_id'] == b['site']['other_highway_id'] and
                b['other_approach_side'] == 'opposite' and
                av['device_qualification_context']['all_sampled_states_off'] and
                bv['device_qualification_context']['all_sampled_states_off'] and
                turn['opposite_approach_with_left_turn_setup'] is True and
                turn['westward_displacement_m'] > 5 and
                turn['southward_displacement_m'] > 5 and
                turn['original_negative_steering_observed'] is True and
                turn['exception_judgment'] == 'unresolved',
                name + ': source-observed opposite left turn missing')
    else:
        raise ValueError('Unknown comparison: ' + name)
    return {'comparison_id': name, 'passed': True,
            'legal_judgment': 'unresolved'}


def audit(root=HERE, plan=None, manifest=None):
    root = Path(root)
    plan = plan or json.loads((root / 'case-plan.json').read_text())
    manifest = manifest or json.loads((root / 'execution-manifest.json').read_text())
    comparisons = plan.get('comparisons', [])
    require({item.get('comparison_id') for item in comparisons} == EXPECTED and
            len(comparisons) == len(EXPECTED), 'Declared comparison coverage differs')
    entries = {item['case_id']: item for item in manifest['cases']}
    require(len(entries) == 5, 'Five exact selected cases required')
    cases = {case: load_case(entry, root) for case, entry in entries.items()}
    results = []
    for item in comparisons:
        ids = item['case_ids']
        require(len(ids) == 2 and ids[0] != ids[1] and
                all(case in cases for case in ids) and
                item.get('fixed_conditions') and item.get('deliberate_differences'),
                'Incomplete comparison declaration')
        results.append(audit_pair(item['comparison_id'], cases[ids[0]], cases[ids[1]]))
    return {'format': 'worker-c125697-comparison-audit', 'passed': True,
            'cases': {case: {'construction_sha256': row['construction_sha256'],
                             'compatibility_sha256': row['compatibility_sha256']}
                      for case, row in cases.items()},
            'comparisons': results,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
