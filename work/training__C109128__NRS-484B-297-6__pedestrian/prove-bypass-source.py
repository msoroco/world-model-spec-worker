"""Construct and exercise the exact synthetic sidewalk-bypass source pair."""
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from bypass import measure, requested, sha


def put(path, rows):
    Path(path).write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


def rejected(path, context):
    try:
        measure(path, context)
    except ValueError as error:
        return str(error)
    raise AssertionError('Malformed bypass source accepted')


def main():
    folder = HERE / 'diagnostic-bypass'
    folder.mkdir(exist_ok=True)
    context = {'context_id': 'c109128-sidewalk-obstruction-v1',
               'sidewalk_id': 'sidewalk_north', 'adjacent_highway_id': 'highway_south',
               'obstruction_id': 'blocked_sidewalk_20_30',
               'sidewalk_y_min_m': 2.0, 'roadway_y_range_m': [0.0, 2.0],
               'obstruction_x_range_m': [20.0, 30.0],
               'obstruction_y_range_m': [2.0, 4.0],
               'physical_obstruction_verified': False,
               'bicycle_lane_designation_verified': False,
               'first_practicable_return_verified': False,
               'original_native_observed': False}
    context_path = folder / 'context.json'
    context_path.write_text(json.dumps(context, indent=2) + '\n')
    records = []
    sources = []
    for condition in ('condition_a', 'condition_b'):
        rows = requested(condition)
        sources.append(rows)
        path = folder / (condition + '.jsonl')
        put(path, rows)
        records.append({'condition': condition, 'source_sha256': sha(path),
                        'measurement': measure(path, context_path)})
    a, b = sources
    changed = [i for i in range(600) if a[i] != b[i]]
    allowed = {'pedestrian_xy_m', 'footprint_xy_m', 'requested_bypass_path'}
    if changed != list(range(600)) or any(
            {k: v for k, v in x.items() if k not in allowed} !=
            {k: v for k, v in y.items() if k not in allowed}
            for x, y in zip(a, b)):
        raise AssertionError('Bypass comparison changed fixed context')
    negative_path = folder / 'negative.jsonl'
    negatives = []
    for name, mutate in (
        ('missing_frame', lambda rows: rows.pop()),
        ('shifted_footprint', lambda rows: rows[220]['footprint_xy_m'][0].__setitem__(1, 1.8)),
        ('wrong_obstruction', lambda rows: rows[220].__setitem__('obstruction_id', 'other')),
        ('teleport', lambda rows: rows[220]['pedestrian_xy_m'].__setitem__(0, 80)),
        ('mixed_path', lambda rows: rows[220].__setitem__('requested_bypass_path', 'condition_b')),
        ('no_road_entry', lambda rows: [row['pedestrian_xy_m'].__setitem__(1, 3.2) for row in rows]),
        ('delayed_return', lambda rows: [rows[i]['pedestrian_xy_m'].__setitem__(1, 1.55) for i in range(400, 500)]),
    ):
        variant = copy.deepcopy(a)
        mutate(variant)
        put(negative_path, variant)
        negatives.append({'mutation': name, 'rejection': rejected(negative_path, context_path)})
    negative_path.unlink()
    bad_context = folder / 'bad-context.json'
    bad_context.write_text(json.dumps(dict(context, physical_obstruction_verified=True)) + '\n')
    negatives.append({'mutation': 'fake_physical_authority',
                      'rejection': rejected(folder / 'condition_a.jsonl', bad_context)})
    bad_context.unlink()
    receipt = {'format': 'c109128-bypass-source-proof-v1',
               'frames_per_condition': 600, 'rate_hz': 20, 'duration_s': 30,
               'controlled_variable': 'pedestrian_bypass_path',
               'fixed_context_keys': sorted(set(a[0]) - allowed),
               'changed_rows': len(changed), 'records': records,
               'negative_rejections': negatives,
               'physical_success_claimed': False, 'legal_verdict_claimed': False,
               'passed': len(negatives) == 8 and
                         records[0]['measurement']['bypass_y_center_m'] !=
                         records[1]['measurement']['bypass_y_center_m']}
    target = HERE / 'bypass-source-proof.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': receipt['passed'], 'receipt_sha256': sha(target),
                      'positives': len(records), 'negatives': len(negatives)}))


if __name__ == '__main__':
    main()
