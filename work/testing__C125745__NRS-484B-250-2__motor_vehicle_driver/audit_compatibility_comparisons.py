"""Audit C125745 comparison measurements in retained compatibility receipts.

This is software source integrity only. Full delivery audit requires accepted
Native recordings with all planned frames and original camera pixels.
"""
import hashlib
import json
import math
import sys
from pathlib import Path
from shapely.geometry import Polygon

HERE = Path(__file__).resolve().parent
EXPECTED = {
    'stop_sign_relative_side': ('stop_ego_left_near_time', 'stop_ego_right_near_time'),
    'stop_sign_entry_timing': ('stop_ego_left_near_time', 'stop_ego_left_separated'),
}

OPPOSITE_CASES = ('stop_ego_left_near_time', 'stop_opposite_left_turn')
OPPOSITE_COMPARISON = 'stop_sign_opposite_approach_context'
QUALITATIVE_COMPARISONS = {
    'stop_sign_opposite_turn_intent':
        ('stop_opposite_left_turn', 'stop_opposite_straight'),
    'stop_sign_entrance_device_presence':
        ('stop_ego_left_near_time', 'stop_ego_left_near_time_no_device'),
}
DEVICE_CASES = ('stop_ego_left_near_time', 'stop_ego_right_near_time',
                'stop_ego_left_separated', 'stop_opposite_left_turn')
SWEEP_AXES = {
    'other_release_frame': ('c125745-1-0000', 'c125745-1-0002', 'c125745-1-0001'),
    'ego_hold_after_clear_frames': ('c125745-2-0000', 'c125745-2-0002', 'c125745-2-0001'),
}
SWEEP_COMPARISONS = {
    'stop_sign_other_release_timing_sweep': 'other_release_frame',
    'stop_sign_ego_hold_timing_sweep': 'ego_hold_after_clear_frames',
}


def require_sweep_declarations(plan):
    declared = {row['comparison_id']: row for row in plan['comparisons']}
    selected = {row['case_id'] for row in plan['cases']}
    required_qualitative = {
        name for name, suffixes in QUALITATIVE_COMPARISONS.items()
        if all(HERE.name + '__' + suffix in selected for suffix in suffixes)}
    require(len(declared) == len(plan['comparisons']) and
            set(declared) == set(EXPECTED) | set(SWEEP_COMPARISONS) |
            {OPPOSITE_COMPARISON} | required_qualitative,
            'Exact declared comparison set required')
    opposite = declared[OPPOSITE_COMPARISON]
    require(opposite['case_ids'] == [HERE.name + '__' + suffix
                                      for suffix in OPPOSITE_CASES] and
            opposite.get('fixed_conditions') and
            opposite.get('deliberate_differences'),
            'Incomplete opposite-context comparison declaration')
    for name, axis in SWEEP_COMPARISONS.items():
        row = declared[name]
        require(row['case_ids'] == [HERE.name + '__' + suffix
                                   for suffix in SWEEP_AXES[axis]] and
                row.get('fixed_conditions') and row.get('deliberate_differences'),
                'Incomplete exact sweep comparison declaration')
    for name in required_qualitative:
        row = declared[name]
        require(row['case_ids'] == [HERE.name + '__' + suffix
                                   for suffix in QUALITATIVE_COMPARISONS[name]] and
                row.get('fixed_conditions') and row.get('deliberate_differences'),
                'Incomplete qualitative comparison declaration')
    return declared


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


def audit_turn_trajectory(context, crossing, controls, frames):
    """Classify observed other-body exit geometry, separately from turn intent."""
    require(context.get('approach_relation') == 'opposite_directions',
            'Opposite approach source required')
    forward = context.get('other_approach_forward_xy')
    require(isinstance(forward, list) and len(forward) == 2 and
            all(isinstance(v, (int, float)) and math.isfinite(v) for v in forward)
            and math.hypot(*forward) > 0, 'Valid source approach vector required')
    polygon = Polygon(context['intersection_polygon_xy_m'])
    require(polygon.is_valid and polygon.area > 0, 'Valid source crossing required')
    require(len(crossing) == len(controls) == len(frames) and len(crossing) >= 2,
            'Complete original source join required')
    positions = []
    inside = []
    previous_frame = -1
    previous_time = float('-inf')
    for i, (body, control, frame_map) in enumerate(zip(crossing, controls, frames)):
        frame, time_s = body['frame'], body['time_s']
        require(frame > previous_frame and time_s > previous_time and
                control['frame'] == frame and frame_map['carla_frame'] == frame and
                frame_map['video_frame'] == i and
                abs(control['time_s'] - time_s) < 1e-9 and
                abs(frame_map['time_s'] - time_s) < 1e-9,
                'Original frame/time join changed')
        require(body.get('other_left_turn_intended') is True and
                control.get('other_left_turn_intended') is True,
                'Recorded left-turn intent required')
        vertices = body['other']['body_vertices_xy_m']
        require(len(vertices) >= 3 and all(len(v) == 2 and
                all(isinstance(x, (int, float)) and math.isfinite(x) for x in v)
                for v in vertices), 'Valid other-body source required')
        shape = Polygon(vertices)
        require(shape.is_valid and shape.area > 0, 'Valid other-body polygon required')
        positions.append((shape.centroid.x, shape.centroid.y))
        inside.append(shape.intersects(polygon))
        previous_frame, previous_time = frame, time_s
    entry = next((i for i, value in enumerate(inside) if value), None)
    require(entry is not None, 'Observed other-body crossing entry required')
    exit_index = next((i for i in range(entry + 1, len(inside)) if not inside[i]), None)
    status = 'unverified'
    signed_turn_deg = None
    if exit_index is not None:
        start = positions[entry]
        end = positions[exit_index]
        dx, dy = end[0] - start[0], end[1] - start[1]
        require(math.hypot(dx, dy) > 0, 'Observed exit displacement required')
        signed_turn_deg = math.degrees(math.atan2(
            forward[0] * dy - forward[1] * dx,
            forward[0] * dx + forward[1] * dy))
        # A geometric diagnostic tolerance, never a statutory turn threshold.
        status = 'met' if signed_turn_deg > 30 else 'not_met'
    return {'format': 'worker-c125745-turn-trajectory-cpu-audit',
            'trajectory_status': status, 'intent_recorded': True,
            'entry_frame': crossing[entry]['frame'],
            'exit_frame': crossing[exit_index]['frame'] if exit_index is not None else None,
            'signed_turn_deg': signed_turn_deg,
            'scope': 'synthetic original-shaped body geometry; 30-degree diagnostic tolerance',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'delivery_ready': False}


def audit_turn_diagnostic(path):
    """Bind a trajectory finding to the retained diagnostic's exact source bytes."""
    diagnostic = read(path)
    recipe = read(path.with_name(path.stem + '-recipe.json'))
    require(recipe['generator']['sha256'] == sha(path),
            'Turn diagnostic hash differs from recipe')
    files = diagnostic['files']
    names = ('junction_context.json', 'crossing_history.jsonl',
             'controller_history.jsonl', 'video_frames.jsonl')
    require(all(name in files for name in names), 'Missing original turn source')
    context = json.loads(files[names[0]])
    rows = [[json.loads(line) for line in files[name].splitlines()] for name in names[1:]]
    result = audit_turn_trajectory(context, *rows)
    result['diagnostic_sha256'] = sha(path)
    result['source_sha256'] = {
        name: hashlib.sha256(files[name].encode()).hexdigest() for name in names}
    return result


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


def compare_exact_sweeps(receipts):
    """Compare the six exact-case compatibility measurements, never legal cutoffs."""
    require(set(receipts) == {suffix for group in SWEEP_AXES.values() for suffix in group},
            'Exact six sweep receipts required')
    axes = []
    for axis, suffixes in SWEEP_AXES.items():
        fixed = None
        measured = []
        for suffix in suffixes:
            receipt = receipts[suffix]
            examples = receipt['measurement_examples']
            require(receipt.get('passed') is True and
                    receipt.get('case_id') == HERE.name + '__' + suffix and
                    receipt.get('negative_removed') == 'controller_history.jsonl',
                    'Exact sweep source and negative proof required')
            for key in ('crossing_identity', 'entry_timing', 'relative_right_side',
                        'device_qualification_context', 'yield_observation'):
                sources = examples[key]['sources']
                require(sources and all(receipt['fixture_manifest'].get(name) == digest
                                        for name, digest in sources.items()),
                        'Sweep measurement source hash differs: ' + key)
            crossing = examples['crossing_identity']['value']
            device = examples['device_qualification_context']['value']
            side = examples['relative_right_side']['value']
            require(crossing['same_statutory_crossing'] is True and
                    side['other_spatially_right'] is True and
                    all(device[key] == 'unresolved' for key in
                        ('official_device_judgment', 'governance_judgment',
                         'subsection_4_judgment')),
                    'Fixed crossing, side or unresolved device context differs')
            context = (crossing['native_map_id'], crossing['intersection_id'],
                       crossing['ego_highway_id'], crossing['other_highway_id'],
                       device['native_stop_sign_id'], side['signed_lateral_offset_m'])
            if fixed is None:
                fixed = context
            require(context == fixed, 'Sweep crossing, sign or approach changed')
            timing = examples['entry_timing']['value']
            ego = timing['first_body_entry']['ego']['frame']
            other = timing['first_body_entry']['other']['frame']
            require(abs(timing['absolute_difference_s'] - abs(ego - other) / 20) < 1e-9 and
                    timing['approximately_same_time_judgment'] == 'unresolved',
                    'Measured entry time or unresolved judgment differs')
            measured.append({'case_id': receipt['case_id'], 'ego_frame': ego,
                             'other_frame': other})
        moving = 'other_frame' if axis == 'other_release_frame' else 'ego_frame'
        stationary = 'ego_frame' if axis == 'other_release_frame' else 'other_frame'
        require([row[moving] for row in measured] ==
                sorted({row[moving] for row in measured}) and
                len({row[stationary] for row in measured}) == 1,
                'Exact sweep did not isolate the measured moving actor')
        axes.append({'axis': axis, 'measured_entries': measured,
                     'fixed_crossing_and_device': True})
    return {'format': 'worker-c125745-exact-sweep-compatibility-audit',
            'axes': axes, 'source_integrity_passed': True,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False, 'delivery_ready': False}


def audit_exact_sweeps():
    require_sweep_declarations(read(HERE / 'case-plan.json'))
    manifest = read(HERE / 'execution-manifest.json')
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    receipts = {}
    for suffix in (item for group in SWEEP_AXES.values() for item in group):
        case_id = HERE.name + '__' + suffix
        entry = entries[case_id]
        path = HERE / entry['compatibility']['receipt']
        require(sha(path) == entry['compatibility']['sha256'],
                'Exact sweep compatibility receipt hash changed')
        receipt = read(path)
        require(receipt['candidate_id'] == 'primary' and
                receipt['construction_sha256'] == entry['construction_sha256'],
                'Exact sweep construction binding changed')
        receipts[suffix] = receipt
    result = compare_exact_sweeps(receipts)
    result['receipt_sha256'] = {suffix: sha(HERE / entries[HERE.name + '__' + suffix]
                                              ['compatibility']['receipt'])
                                for suffix in receipts}
    return result


def audit():
    manifest = read(HERE / 'execution-manifest.json')
    plan = read(HERE / 'case-plan.json')
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    declared = require_sweep_declarations(plan)
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
    require(opposite_context['case_ids'] == declared[OPPOSITE_COMPARISON]['case_ids'],
            'Opposite-context comparison case binding changed')
    opposite_context['comparison_id'] = OPPOSITE_COMPARISON
    all_receipts = dict(receipts)
    all_receipts[opposite_id] = opposite_receipt
    device_context = audit_device_context({
        suffix: all_receipts[HERE.name + '__' + suffix]
        for suffix in DEVICE_CASES})
    sweep_comparisons = audit_exact_sweeps()
    from audit_turn_delivery import audit as audit_turn_pair
    from audit_device_delivery import audit as audit_device_pair
    qualitative = {
        'stop_sign_opposite_turn_intent': audit_turn_pair(HERE),
        'stop_sign_entrance_device_presence': audit_device_pair(HERE),
    }
    for name, proof in qualitative.items():
        require(proof['case_ids'] == declared[name]['case_ids'] and
                proof['recorded_only_passed'] is True and
                proof['physical_acceptance_claimed'] is False,
                'Selected qualitative comparison proof differs')
    return {'format': 'worker-c125745-compatibility-comparison-audit',
            'software_comparisons_passed': True, 'comparisons': pairs,
            'sweep_comparisons': sweep_comparisons,
            'opposite_context': opposite_context,
            'device_context': device_context,
            'qualitative_comparisons': qualitative,
            'scope': 'retained synthetic original-source compatibility receipts',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'delivery_ready': False}


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--turn-diagnostic':
        print(json.dumps(audit_turn_diagnostic(Path(sys.argv[2])), indent=2))
    elif len(sys.argv) == 2 and sys.argv[1] == '--exact-sweeps':
        print(json.dumps(audit_exact_sweeps(), indent=2))
    else:
        require(len(sys.argv) == 1, 'Usage: audit_compatibility_comparisons.py [--turn-diagnostic PATH] [--exact-sweeps]')
        print(json.dumps(audit(), indent=2))
