"""Audit C125745 comparison measurements in retained compatibility receipts.

This is software source integrity only. Full delivery audit requires accepted
Native recordings with all planned frames and original camera pixels.
"""
import hashlib
import json
from pathlib import Path
from shapely.geometry import Polygon

HERE = Path(__file__).resolve().parent
EXPECTED = {
    'stop_sign_relative_side': ('stop_ego_left_near_time', 'stop_ego_right_near_time'),
    'stop_sign_entry_timing': ('stop_ego_left_near_time', 'stop_ego_left_separated'),
}

OPPOSITE_CASES = ('stop_ego_left_near_time', 'stop_opposite_left_turn')
DEVICE_CASES = ('stop_ego_left_near_time', 'stop_ego_right_near_time',
                'stop_ego_left_separated', 'stop_opposite_left_turn')


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_surrogate_grid(points, axis):
    """Independently remeasure CPU command/body source grids; no physical claim."""
    expected = {'other_release_frame': (32, 40, 48),
                'ego_hold_after_clear_frames': (0, 8, 16)}
    require(axis in expected and set(points) == set(expected[axis]),
            'Exact surrogate grid points required')
    measurements = []
    fixed_context = None
    fixed_commands = None
    for value in expected[axis]:
        diagnostic = Path(points[value])
        recipe = read(diagnostic.with_name(diagnostic.stem + '-recipe.json'))
        require(recipe['generator']['sha256'] == sha(diagnostic),
                'Surrogate diagnostic hash differs from recipe')
        spec = read(diagnostic)
        files = spec['files']
        required = ('junction_context.json', 'crossing_history.jsonl',
                    'video_frames.jsonl', 'controller_history.jsonl', 'trace.jsonl')
        require(all(name in files for name in required), 'Missing original surrogate source')
        context = json.loads(files['junction_context.json'])
        identity = tuple(context[key] for key in
                         ('native_map_id', 'intersection_id', 'native_stop_sign_id'))
        if fixed_context is None:
            fixed_context = identity
        require(identity == fixed_context, 'Fixed source crossing or sign changed')
        rows = [[json.loads(line) for line in files[name].splitlines()]
                for name in required[1:]]
        crossing, mapping, controls, trace = rows
        require(len(crossing) == len(mapping) == len(controls) == len(trace) == 135,
                'Incomplete 135-frame source join')
        polygon = Polygon(context['intersection_polygon_xy_m'])
        first = {}
        for i, (body, frame_map, command, pose) in enumerate(zip(*rows)):
            frame = body['frame']
            require(frame_map['video_frame'] == i and frame_map['carla_frame'] == frame
                    and command['frame'] == frame and pose['frame'] == frame,
                    'Original frame join changed')
            require(abs(body['time_s']-frame_map['time_s']) < 1e-9 and
                    abs(body['time_s']-command['time_s']) < 1e-9,
                    'Original timestamps changed')
            for role in ('ego', 'other'):
                vertices = body[role]['body_vertices_xy_m']
                if role not in first and Polygon(vertices).intersects(polygon):
                    first[role] = frame
        require(set(first) == {'ego', 'other'}, 'Both original body entries required')
        role = 'other' if axis == 'other_release_frame' else 'ego'
        onset = next((i for i, command in enumerate(controls)
                      if command['commands'][role]['throttle'] > 0), None)
        require(onset == (value if role == 'other' else 80 + value),
                'Control onset does not match sweep point')
        constant_role = 'ego' if role == 'other' else 'other'
        commands = [row['commands'][constant_role] for row in controls]
        if fixed_commands is None:
            fixed_commands = commands
        require(commands == fixed_commands, 'Fixed actor commands changed across sweep')
        measurements.append({'setpoint_frames': value, 'first_body_entry_frames': first,
                             'diagnostic_sha256': sha(diagnostic)})
    moving = 'other' if axis == 'other_release_frame' else 'ego'
    fixed = 'ego' if moving == 'other' else 'other'
    require([m['first_body_entry_frames'][moving] for m in measurements] ==
            sorted(m['first_body_entry_frames'][moving] for m in measurements)
            and len({m['first_body_entry_frames'][moving] for m in measurements}) == 3,
            'Commanded sweep did not move measured entry')
    require(len({m['first_body_entry_frames'][fixed] for m in measurements}) == 1,
            'Fixed actor entry changed across sweep')
    return {'format': 'worker-c125745-surrogate-grid-audit', 'axis': axis,
            'points': measurements, 'source_integrity_passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'delivery_ready': False}


def audit_opposite_context(receipts):
    """Compare source-bound approach context; retain the turn judgment as open."""
    require(set(receipts) == set(OPPOSITE_CASES), 'Exact opposite-context receipt pair required')
    rows = [receipts[suffix] for suffix in OPPOSITE_CASES]
    for suffix, receipt in zip(OPPOSITE_CASES, rows):
        require(receipt.get('passed') is True and
                receipt.get('case_id') == HERE.name + '__' + suffix and
                receipt.get('negative_removed') == 'controller_history.jsonl',
                'Exact source-bound opposite-context receipt required')
        examples = receipt.get('measurement_examples', {})
        for key in ('crossing_identity', 'device_qualification_context',
                    'opposite_left_turn_context', 'entry_timing'):
            require(examples.get(key, {}).get('sources'),
                    'Missing original source hashes for ' + key)
    left, opposite = (row['measurement_examples'] for row in rows)
    a, b = left['crossing_identity']['value'], opposite['crossing_identity']['value']
    require(all(a[k] == b[k] for k in
                ('native_map_id', 'intersection_id', 'ego_highway_id',
                 'same_statutory_crossing')) and
            a['other_highway_id'] != b['other_highway_id'] and
            b['other_highway_id'] == b['ego_highway_id'],
            'Fixed crossing or opposite-highway contrast missing')
    device_a, device_b = (x['device_qualification_context']['value']
                          for x in (left, opposite))
    require(device_a == device_b and device_a['native_stop_sign_id'] == 17 and
            device_a['official_device_judgment'] == 'unresolved' and
            device_a['governance_judgment'] == 'unresolved',
            'Fixed stop-sign identity or unresolved device review changed')
    approach_a, approach_b = (x['opposite_left_turn_context']['value']
                              for x in (left, opposite))
    require(approach_a['opposite_approach'] is False and
            approach_b['opposite_approach'] is True and
            approach_a['exception_judgment'] == approach_b['exception_judgment'] == 'unresolved',
            'Opposite approach or unresolved turn judgment changed')
    time_a, time_b = (x['entry_timing']['value']['absolute_difference_s']
                      for x in (left, opposite))
    require(abs(time_a - time_b) < 1e-9,
            'Fixed measured entry timing changed')
    return {'format': 'worker-c125745-opposite-context-audit',
            'case_ids': [row['case_id'] for row in rows],
            'fixed_crossing_and_sign_passed': True,
            'opposite_approach_contrast_passed': True,
            'turn_intention_judgment': 'unresolved',
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False, 'delivery_ready': False}


def audit_device_context(receipts):
    """Check source-backed device identity across selected alternatives."""
    require(set(receipts) == set(DEVICE_CASES), 'Exact device-context receipt set required')
    observed = []
    for suffix in DEVICE_CASES:
        receipt = receipts[suffix]
        require(receipt.get('passed') is True and
                receipt.get('case_id') == HERE.name + '__' + suffix and
                receipt.get('negative_removed') == 'controller_history.jsonl',
                'Exact source-bound device-context receipt required')
        examples = receipt.get('measurement_examples', {})
        device = examples.get('device_qualification_context', {})
        require(set(device.get('sources', {})) ==
                {'junction_context.json', 'crossing_history.jsonl'},
                'Device context lacks original source hashes')
        require(all(name + '.mkv' in receipt.get('fixture_manifest', {})
                    for name in ('overview', 'approach', 'reference_corner', 'driver_reference')),
                'Device context lacks four original camera sources')
        observed.append(device.get('value'))
    require(all(value == observed[0] for value in observed) and
            observed[0]['native_stop_sign_id'] == 17 and
            all(observed[0][key] == 'unresolved' for key in
                ('official_device_judgment', 'governance_judgment',
                 'subsection_4_judgment')),
            'Fixed sign identity or unresolved official-device review changed')
    return {'format': 'worker-c125745-device-context-audit',
            'case_ids': [receipts[suffix]['case_id'] for suffix in DEVICE_CASES],
            'fixed_sign_and_source_contract_passed': True,
            'official_device_judgment': 'unresolved',
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False, 'delivery_ready': False}


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
    opposite_id = HERE.name + '__stop_opposite_left_turn'
    opposite_entry = entries[opposite_id]
    opposite_path = HERE / opposite_entry['compatibility']['receipt']
    require(sha(opposite_path) == opposite_entry['compatibility']['sha256'],
            'Opposite-context compatibility receipt hash changed')
    opposite_receipt = read(opposite_path)
    require(opposite_receipt['construction_sha256'] == opposite_entry['construction_sha256'],
            'Opposite-context construction receipt changed')
    opposite_context = audit_opposite_context({
        'stop_ego_left_near_time': receipts[HERE.name + '__stop_ego_left_near_time'],
        'stop_opposite_left_turn': opposite_receipt})
    all_receipts = dict(receipts)
    all_receipts[opposite_id] = opposite_receipt
    device_context = audit_device_context({
        suffix: all_receipts[HERE.name + '__' + suffix]
        for suffix in DEVICE_CASES})
    return {'format': 'worker-c125745-compatibility-comparison-audit',
            'software_comparisons_passed': True, 'comparisons': pairs,
            'opposite_context': opposite_context,
            'device_context': device_context,
            'scope': 'retained synthetic original-source compatibility receipts',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
