"""Independent fixed-topology entry-order audit for the ending-road branch."""

import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
import shlex
import sys
from tempfile import TemporaryDirectory

from ending_road_measurement import measure
from importlib.util import module_from_spec, spec_from_file_location


def measure_opposing_left(root):
    source = Path(root) / 'opposing_left_measurement.py'
    if not source.is_file():
        source = Path('.runtime-work/c295149-opposing-left-primary-saved-attempt-1/opposing_left_measurement.py')
    spec = spec_from_file_location('opposing_left_measurement', source)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.measure_opposing_left(root)


def audit(yield_case, proceed_case):
    left, right = Path(yield_case), Path(proceed_case)
    topology_name = 'intersection_topology.json'
    trace_name = 'intersection_participants.jsonl'
    for root in (left, right):
        for name in (topology_name, trace_name):
            if not (root / name).is_file():
                raise ValueError('Missing exact comparison original: ' + name)
    if sha256((left / topology_name).read_bytes()).digest() != sha256((right / topology_name).read_bytes()).digest():
        raise ValueError('Entry-order comparison changed fixed lane topology')
    first = []
    for root in (left, right):
        rows = [json.loads(line) for line in (root / trace_name).read_text().splitlines()]
        if not rows:
            raise ValueError('Entry-order comparison has no original frames')
        first.append(rows[0])
    for name in ('subject_id', 'other_id', 'subject_corners', 'other_corners'):
        if first[0].get(name) != first[1].get(name):
            raise ValueError('Entry-order comparison changed initial actor setup: ' + name)
    yielded = measure(left / topology_name, left / trace_name)
    proceeded = measure(right / topology_name, right / trace_name)
    if not yielded['subject_entered_after_other_last_conflict_frame']:
        raise ValueError('Yield case does not contain a measured delayed entry')
    if proceeded['subject_entered_after_other_last_conflict_frame']:
        raise ValueError('Proceed case did not change measured entry order')
    return {'passed': True, 'comparison_id': 'ending_through_yield_order',
            'yield_entry_delta_s': yielded['entry_delta_s'],
            'proceed_entry_delta_s': proceeded['entry_delta_s'],
            'legal_acceptance_claimed': False}


def _sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _selected(manifest, suffix):
    here = Path(__file__).resolve().parent
    entry = next((row for row in manifest['cases']
                  if row['case_id'] == here.name + '__' + suffix), None)
    if entry is None:
        raise ValueError('Missing selected exact comparison member: ' + suffix)
    tokens = shlex.split(entry['saved_processing_proof']['command'])
    attempt = Path(tokens[tokens.index('--attempt') + 1])
    receipt_path = here / entry['saved_processing_proof']['log']
    receipt = json.loads(receipt_path.read_text())
    if (not receipt.get('passed') or receipt.get('missing_evidence')
            or not receipt.get('recorded_only')
            or receipt.get('case_id') != entry['case_id']
            or receipt.get('candidate_id') != 'primary'
            or receipt['native_revision']['construction_sha256'] != entry['construction_sha256']
            or _sha(receipt_path) != entry['saved_processing_proof']['log_sha256']):
        raise ValueError('Exact saved source receipt differs: ' + suffix)
    for name in ('intersection_topology.json', 'intersection_participants.jsonl',
                 'video_frames.jsonl', 'trace.jsonl') + tuple(
                     name for name in ('official_device_context.json',
                                       'official_geometry_binding.json',
                                       'official_device_states.jsonl')
                     if (attempt / name).is_file()):
        if _sha(attempt / name) != receipt['original_source_hashes'][name]:
            raise ValueError('Original source hash differs: ' + suffix + '/' + name)
    if _sha(receipt['result']) != receipt['result_sha256']:
        raise ValueError('Saved measurement hash differs: ' + suffix)
    return attempt, {'case_id': entry['case_id'], 'saved_receipt_sha256': _sha(receipt_path),
                     'topology_sha256': _sha(attempt / 'intersection_topology.json'),
                     'participants_sha256': _sha(attempt / 'intersection_participants.jsonl')}


def audit_exact(comparison_id, *, tamper=False):
    """Audit exact retained originals; synthetic fixtures make no legal finding."""
    if comparison_id == 'release_controller_sweep':
        return audit_release_controller_sweep(tamper=tamper)
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / 'execution-manifest.json').read_text())
    plan = json.loads((here / 'case-plan.json').read_text())
    spec = next((row for row in plan['comparisons']
                 if row['comparison_id'] == comparison_id), None)
    if comparison_id == 'opposing_left_exception' and spec is not None:
        return _audit_opposing_probe(manifest, spec, tamper=tamper)
    if spec is None or comparison_id not in ('ending_yield_order', 'arrival_window',
                                            'official_control'):
        raise ValueError('Unsupported exact source comparison: ' + comparison_id)
    suffixes = [case.rsplit('__', 1)[-1] for case in spec['case_ids']]
    (left, left_proof), (right, right_proof) = [_selected(manifest, s) for s in suffixes]
    topology = 'intersection_topology.json'
    participants = 'intersection_participants.jsonl'
    if comparison_id == 'official_control':
        if tamper:
            with TemporaryDirectory(prefix='c295149-device-tamper-') as temporary:
                substitute = Path(temporary)
                for name in ('intersection_topology.json',
                             'official_geometry_binding.json',
                             'official_device_context.json',
                             'official_device_states.jsonl', 'video_frames.jsonl'):
                    (substitute / name).write_bytes((right / name).read_bytes())
                modified = json.loads((substitute / 'official_device_context.json').read_text())
                modified['device_id'] = 'tampered-device'
                (substitute / 'official_device_context.json').write_text(json.dumps(modified) + '\n')
                _compare_official(left, substitute)
            raise AssertionError('Fixed-device tamper unexpectedly passed')
        measured = _compare_official(left, right)
        return {'comparison_id': comparison_id, 'case_ids': spec['case_ids'],
                'source_receipts': [left_proof, right_proof], 'measurement': measured,
                'fixed_device_and_geometry_verified': True,
                'synthetic_diagnostic_only': True, 'physical_acceptance_claimed': False,
                'legal_acceptance_claimed': False}
    if tamper:
        with TemporaryDirectory(prefix='c295149-comparison-tamper-') as temporary:
            substitute = Path(temporary)
            (substitute / participants).write_bytes((right / participants).read_bytes())
            modified = json.loads((right / topology).read_text())
            modified['junction_id'] = 'tampered-junction'
            (substitute / topology).write_text(json.dumps(modified) + '\n')
            _compare_sources(comparison_id, left, substitute)
        raise AssertionError('Fixed-topology tamper unexpectedly passed')
    measured = _compare_sources(comparison_id, left, right)
    return {'comparison_id': comparison_id, 'case_ids': spec['case_ids'],
            'source_receipts': [left_proof, right_proof], 'measurement': measured,
            'fixed_topology_verified': True, 'original_participants_verified': True,
            'synthetic_diagnostic_only': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def _compare_sources(comparison_id, left, right):
    topology = 'intersection_topology.json'
    participants = 'intersection_participants.jsonl'
    if _sha(left / topology) != _sha(right / topology):
        raise ValueError('Controlled comparison changed fixed lane topology')
    first = []
    for root in (left, right):
        rows = [json.loads(line) for line in (root / participants).read_text().splitlines()]
        if not rows:
            raise ValueError('Controlled comparison lacks original participant frames')
        first.append(rows[0])
    for key in ('subject_id', 'other_id', 'subject_corners', 'other_corners'):
        if first[0].get(key) != first[1].get(key):
            raise ValueError('Controlled comparison changed initial actor setup: ' + key)
    a = measure(left / topology, left / participants)
    b = measure(right / topology, right / participants)
    if comparison_id == 'ending_yield_order':
        if not a['subject_entered_after_other_last_conflict_frame'] or b['subject_entered_after_other_last_conflict_frame']:
            raise ValueError('Original entry order did not change as selected')
    elif comparison_id == 'arrival_window':
        if a['entry_delta_s'] == b['entry_delta_s']:
            raise ValueError('Original arrival window did not change')
    return {'entry_delta_s': [a['entry_delta_s'], b['entry_delta_s']],
            'subject_entry_frame': [a['subject_entry_frame'], b['subject_entry_frame']],
            'other_entry_frame': [a['other_entry_frame'], b['other_entry_frame']],
            'legal_approximately_same_time': None}


def _compare_official(active, inoperative):
    fixed = ('intersection_topology.json', 'official_geometry_binding.json',
             'official_device_context.json')
    for name in fixed:
        if _sha(active / name) != _sha(inoperative / name):
            raise ValueError('Official comparison changed fixed source: ' + name)
    contexts = [json.loads((root / 'official_device_context.json').read_text())
                for root in (active, inoperative)]
    if contexts[0]['legal_official_status_claimed'] or contexts[1]['legal_official_status_claimed']:
        raise ValueError('Diagnostic device source cannot claim legal official status')
    states = []
    for root, context in zip((active, inoperative), contexts):
        rows = [json.loads(line) for line in
                (root / 'official_device_states.jsonl').read_text().splitlines()]
        frames = [json.loads(line) for line in
                  (root / 'video_frames.jsonl').read_text().splitlines()]
        if not rows or len(rows) != len(frames):
            raise ValueError('Official comparison lacks synchronized original state')
        if any(row['device_id'] != context['device_id'] or
               row['frame'] != frame['carla_frame'] or
               abs(row['time_s'] - frame['time_s']) > 1e-4
               for row, frame in zip(rows, frames)):
            raise ValueError('Official comparison changed device or frame join')
        values = {row['native_state'] for row in rows}
        if len(values) != 1:
            raise ValueError('Official comparison state changed within capture')
        states.append(next(iter(values)))
    if states != ['TrafficLightState.Red', 'TrafficLightState.Off']:
        raise ValueError('Official comparison did not isolate operating state')
    return {'native_states': states, 'device_id': contexts[0]['device_id'],
            'state_source_sha256': [_sha(root / 'official_device_states.jsonl')
                                    for root in (active, inoperative)],
            'legal_official_status': None}


def _audit_opposing_probe(manifest, spec, *, tamper):
    """Check the distinct-source exception probe without claiming a causal pair."""
    here = Path(__file__).resolve().parent
    suffix = spec['case_ids'][1].rsplit('__', 1)[-1]
    entry = next((row for row in manifest['cases'] if row['case_id'] == spec['case_ids'][1]), None)
    if entry is None:
        raise ValueError('Missing selected opposing-left case')
    tokens = shlex.split(entry['saved_processing_proof']['command'])
    original = Path(tokens[tokens.index('--attempt') + 1])
    receipt_path = here / entry['saved_processing_proof']['log']
    receipt = json.loads(receipt_path.read_text())
    if (not receipt.get('passed') or receipt.get('missing_evidence')
            or not receipt.get('recorded_only') or receipt.get('candidate_id') != 'primary'
            or receipt.get('case_id') != entry['case_id']
            or receipt['native_revision']['construction_sha256'] != entry['construction_sha256']
            or _sha(receipt_path) != entry['saved_processing_proof']['log_sha256']
            or _sha(receipt['result']) != receipt['result_sha256']):
        raise ValueError('Opposing-left saved receipt differs')
    sources = ('opposing_left_context.json', 'opposing_left_participants.jsonl',
               'video_frames.jsonl', 'trace.jsonl')
    for name in sources:
        if _sha(original / name) != receipt['original_source_hashes'][name]:
            raise ValueError('Opposing-left original hash differs: ' + name)
    if tamper:
        with TemporaryDirectory(prefix='c295149-opposing-tamper-') as temporary:
            substitute = Path(temporary)
            for name in sources:
                (substitute / name).write_bytes((original / name).read_bytes())
            context = json.loads((substitute / sources[0]).read_text())
            context['opposite_route'][0]['heading_xy'] = [-1, 0]
            (substitute / sources[0]).write_text(json.dumps(context) + '\n')
            measure_opposing_left(substitute)
        raise AssertionError('Opposing-route tamper unexpectedly passed')
    measurement = measure_opposing_left(original)
    value = measurement['value']
    saved = json.loads((original / 'result.json').read_text())['measured_values']['opposing_left_observation']
    if value != saved or value['approach_heading_dot'] > -.8 or value['planned_left_cross'] < .5:
        raise ValueError('Opposing-left source measurement differs from saved result')
    return {'comparison_id': spec['comparison_id'], 'case_ids': spec['case_ids'],
            'comparison_kind': 'exception probe; topology differs by design',
            'opposing_source_receipt_sha256': _sha(receipt_path),
            'original_source_hashes': {name: _sha(original / name) for name in sources},
            'measurement': value, 'synthetic_diagnostic_only': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def audit_release_controller_sweep(*, tamper=False):
    """Check returned controller alternatives without claiming observed Native motion."""
    here = Path(__file__).resolve().parent
    constructions = []
    fixed_files = None
    normalized_runners = None
    for delay in (0, 4, 8):
        primary = json.loads((here / f'construction-yield-release-delay-{delay}.json').read_text())
        primary_files = {row['path']: row['content'] for row in primary['files']}
        base = json.loads(primary_files['config.json'])
        expected_case = here.name + f'__yield_release_delay_{delay}'
        if (primary['case_id'] != expected_case or
                base['selected_case_id'] != expected_case or
                base['case']['case_id'] != expected_case or
                base['subject_release_delay_frames'] != delay):
            raise ValueError('Release sweep primary identity or delay differs')
        for candidate in range(4):
            name = (f'construction-yield-release-delay-{delay}.json' if candidate == 0
                    else f'construction-yield-release-delay-{delay}-fallback{candidate}.json')
            path = here / name
            construction = json.loads(path.read_text())
            files = {row['path']: row['content'] for row in construction['files']}
            config = json.loads(files['config.json'])
            expected = json.loads(json.dumps(base))
            if candidate == 1:
                expected['max_spawns'] = 600
            elif candidate == 2:
                expected['yield_clearance_m'] = 4
            elif candidate == 3:
                expected['frames'] = 240
                expected['duration_s'] = 12
                expected['case']['recording_description']['channels'][0]['time_window'] = 'full 12 s trace'
            if tamper and delay == 8 and candidate == 2:
                config['subject_release_delay_frames'] = 7
            if construction['case_id'] != expected_case or config != expected:
                raise ValueError('Release sweep candidate changes an unplanned condition: ' + name)
            common = {key: value for key, value in files.items()
                      if key not in ('config.json', 'ending_road_runner.py', 'runner.py',
                                     'tests/test_ending_road_runner.py')}
            if fixed_files is None:
                fixed_files = common
            elif common != fixed_files:
                raise ValueError('Release sweep changes fixed construction source: ' + name)
            runners = tuple(files[key].replace(f'yield_release_delay_{delay}', 'yield_release_delay_N')
                            for key in ('ending_road_runner.py', 'runner.py'))
            if normalized_runners is None:
                normalized_runners = runners
            elif runners != normalized_runners:
                raise ValueError('Release sweep changes controller source: ' + name)
            tree = ast.parse(files['ending_road_runner.py'])
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'release_ready']
            if len(calls) != 1 or [ast.unparse(arg) for arg in calls[0].args] != [
                    'tick_index', 'release_eligible_tick', "config['subject_release_delay_frames']"]:
                raise ValueError('Release sweep no longer uses configured delay: ' + name)
            function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                            and node.name == 'release_ready')
            namespace = {}
            exec(compile(ast.Module(body=[function], type_ignores=[]), name, 'exec'), namespace)
            ready = namespace['release_ready']
            if (ready(6, None, delay) or ready(5, 6, delay)
                    or not ready(6 + delay, 6, delay)
                    or (delay and ready(5 + delay, 6, delay))):
                raise ValueError('Release sweep controller boundary differs: ' + name)
            constructions.append({'case_id': expected_case, 'candidate': candidate,
                                  'construction': name, 'sha256': _sha(path)})
    return {'passed': True, 'comparison_id': 'release_controller_sweep',
            'release_ticks_after_eligibility': [0, 4, 8],
            'constructions': constructions, 'fixed_embedded_sources_verified': True,
            'native_motion_observed': False, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def audit_release_motion_diagnostic(output, *, tamper=False):
    """Generate and measure joined synthetic timing source records.

    The authored tracks test source measurement sensitivity. They are not
    original Native motion or four-camera compatibility fixtures.
    """
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent
    fixture = json.loads((here / 'diagnostic-ending-yields.json').read_text())
    topology_bytes = fixture['files']['intersection_topology.json'].encode()
    topology = json.loads(topology_bytes)
    if topology['conflict_polygon_xy'] != [[-1, -1], [1, -1], [1, 1], [-1, 1]]:
        raise ValueError('Diagnostic conflict geometry changed')
    measured = []
    first_rows = []
    for delay in (0, 4, 8):
        folder = root / f'delay-{delay}'
        folder.mkdir(exist_ok=True)
        (folder / 'intersection_topology.json').write_bytes(topology_bytes)
        rows = []
        trace_rows = []
        frame_rows = []
        for tick in range(32):
            frame, time_s = 38033 + tick, .05 * (tick + 1)
            other_y = min(-2.5 + .5 * tick, 4)
            subject_x = (-2.5 if tick < 12 + delay else
                         min(-2 + .5 * (tick - 12 - delay), 4))
            def box(x, y):
                return [[x - .4, y - .4], [x + .4, y - .4],
                        [x + .4, y + .4], [x - .4, y + .4]]
            rows.append({'frame': frame, 'time_s': time_s,
                         'subject_id': topology['subject_id'],
                         'other_id': topology['other_id'],
                         'subject_corners': box(subject_x, 0),
                         'other_corners': box(0, other_y)})
            trace_rows.append({'frame': frame, 'time_s': time_s,
                               'position_m': [subject_x, 0, 0],
                               'velocity_mps': [10 if tick >= 12 + delay and subject_x < 4 else 0, 0, 0],
                               'control': {'throttle': .5 if tick >= 12 + delay else 0,
                                           'brake': 0 if tick >= 12 + delay else 1}})
            frame_rows.append({'video_frame': tick, 'carla_frame': frame,
                               'native_frame': frame, 'time_s': time_s})
        if tamper and delay == 8:
            rows[0]['subject_corners'][0][0] -= 1
            trace_rows[0]['position_m'][0] -= 1
        (folder / 'intersection_participants.jsonl').write_text(
            ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
        (folder / 'trace.jsonl').write_text(
            ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in trace_rows))
        (folder / 'video_frames.jsonl').write_text(
            ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in frame_rows))
        first_rows.append(rows[0])
        result = measure(folder / 'intersection_topology.json',
                         folder / 'intersection_participants.jsonl')
        if result['subject_entry_frame'] != 38033 + 14 + delay:
            raise ValueError('Diagnostic measured entry does not follow release delay')
        if any((row['frame'] != trace['frame'] or row['frame'] != frames['carla_frame']
                or row['time_s'] != trace['time_s'] or row['time_s'] != frames['time_s']
                or abs(trace['position_m'][0] - (row['subject_corners'][0][0] + .4)) > 1e-8)
               for row, trace, frames in zip(rows, trace_rows, frame_rows)):
            raise ValueError('Diagnostic participant/trace/frame source join differs')
        measured.append({'delay_frames': delay,
                         'subject_entry_frame': result['subject_entry_frame'],
                         'other_entry_frame': result['other_entry_frame'],
                         'entry_delta_s': result['entry_delta_s'],
                         'topology_sha256': result['topology_sha256'],
                         'participants_sha256': result['frames_sha256']})
    if any(first_rows[0] != row for row in first_rows[1:]):
        raise ValueError('Diagnostic changed initial actor setup')
    if len({row['topology_sha256'] for row in measured}) != 1:
        raise ValueError('Diagnostic changed fixed topology')
    if [row['subject_entry_frame'] for row in measured] != [38047, 38051, 38055]:
        raise ValueError('Diagnostic did not change measured entry timing')
    return {'passed': True, 'comparison_id': 'release_motion_diagnostic',
            'authored_clearance_eligibility_tick': 12,
            'measurements': measured, 'source_records_only_synthetic_diagnostic': True,
            'four_camera_compatibility_proven': False, 'native_motion_observed': False,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def audit_physical_outcomes(*, tamper=False):
    """Exercise the pinned motion assessor for every selected exact case.

    This checks the assessor's three outcomes on authored source rows. It does
    not use a fixture label as an input to the assessor or imply Native motion.
    """
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    sys.path.insert(0, str(root / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.native_output import assess_physical, default_descriptor

    manifest = json.loads((here / 'execution-manifest.json').read_text())
    results = []
    for entry in manifest['cases']:
        construction = json.loads((here / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        descriptor = default_descriptor(config)
        if descriptor['criterion'] != 'travel_progress':
            raise ValueError('Selected case needs a different physical fixture')
        count = round(float(config['duration_s']) * float(config['rate_hz']))
        if count < 3:
            raise ValueError('Selected capture is too short for motion assessment')
        observed = {}
        for kind, factor in (('complete_motion', 1.5),
                             ('incomplete_motion', .1),
                             ('missing_evidence', 1.5)):
            with TemporaryDirectory(prefix='c295149-physical-',
                                    dir=root / '.runtime-work') as temporary:
                folder = Path(temporary)
                distance = descriptor['minimum_progress_m'] * factor
                (folder / 'config.json').write_text(json.dumps(config) + '\n')
                frames = [{'carla_frame': 42000 + i,
                           'time_s': i / float(config['rate_hz'])}
                          for i in range(count)]
                (folder / 'video_frames.jsonl').write_text(''.join(
                    json.dumps(row) + '\n' for row in frames))
                if kind != 'missing_evidence':
                    trace = [{'frame': row['carla_frame'],
                              'time_s': row['time_s'],
                              'position_m': [distance * i / (count - 1), 0, 0]}
                             for i, row in enumerate(frames)]
                    if tamper and kind == 'complete_motion' and entry == manifest['cases'][-1]:
                        trace[-1]['frame'] += 1
                    (folder / 'trace.jsonl').write_text(''.join(
                        json.dumps(row) + '\n' for row in trace))
                result = assess_physical(folder, config)
                actual = result['physical_checks']['maneuver']['status']
                expected = {'complete_motion': 'met',
                            'incomplete_motion': 'not_met',
                            'missing_evidence': 'unverified'}[kind]
                if actual != expected or result['maneuver_completed'] != (expected == 'met'):
                    raise ValueError('Physical source outcome differs: '
                                     + entry['case_id'] + ' ' + kind + ' ' + actual)
                if expected == 'met' and not result['realized_observables']:
                    raise ValueError('Completed motion lacks measured observations')
                observed[kind] = actual
        results.append({'case_id': entry['case_id'],
                        'construction_sha256': entry['construction_sha256'],
                        'outcomes': observed,
                        'engineering_minimum_progress_m': descriptor['minimum_progress_m']})
    return {'passed': True, 'comparison_id': 'physical_outcome_diagnostic',
            'cases': results, 'synthetic_fixture': True,
            'native_motion_observed': False, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def physical_fixture(case_id, kind, *, tamper=False):
    """Save one exact case's pinned physical assessment or lifecycle test."""
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    manifest = json.loads((here / 'execution-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Unknown selected physical fixture case')
    if kind == 'lifecycle':
        events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']
        def valid(rows):
            return (rows.index('capture_finished') < rows.index('encoders_closed')
                    < rows.index('restoration_verified') < rows.index('native_exit')
                    < rows.index('owner_released') < rows.index('saved_processing_started'))
        early = events.copy()
        early[3], early[4] = early[4], early[3]
        if tamper:
            if valid(early):
                raise AssertionError('Premature owner release was accepted')
            raise ValueError('Premature owner release rejected')
        if not valid(events) or valid(early):
            raise AssertionError('Lifecycle ordering test failed')
        return {'case_id': case_id, 'events': events,
                'premature_owner_release_rejected': True,
                'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown physical fixture kind')
    construction = json.loads((here / entry['construction']).read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    sys.path.insert(0, str(root / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.native_output import assess_physical, default_descriptor
    descriptor = default_descriptor(config)
    if descriptor['criterion'] != 'travel_progress':
        raise ValueError('Unsupported selected physical criterion')
    count = round(float(config['duration_s']) * float(config['rate_hz']))
    if count < 3:
        raise ValueError('Selected capture too short for physical assessment')
    with TemporaryDirectory(prefix='c295149-physical-', dir=root / '.runtime-work') as temp:
        folder = Path(temp)
        (folder / 'config.json').write_text(json.dumps(config, sort_keys=True) + '\n')
        frames = [{'carla_frame': 42000 + i, 'time_s': i / float(config['rate_hz'])}
                  for i in range(count)]
        (folder / 'video_frames.jsonl').write_text(''.join(
            json.dumps(row) + '\n' for row in frames))
        if kind != 'missing_evidence':
            factor = 1.5 if kind == 'complete_motion' else .1
            distance = descriptor['minimum_progress_m'] * factor
            trace = [{'frame': row['carla_frame'], 'time_s': row['time_s'],
                      'position_m': [distance * i / (count - 1), 0, 0]}
                     for i, row in enumerate(frames)]
            if tamper:
                trace[-1]['frame'] += 1
            (folder / 'trace.jsonl').write_text(''.join(
                json.dumps(row) + '\n' for row in trace))
        assessed = assess_physical(folder, config)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if assessed['physical_checks']['maneuver']['status'] != expected:
        raise ValueError('Physical assessment differs from authored source outcome')
    if assessed['maneuver_completed'] != (expected == 'met'):
        raise ValueError('Physical completion boolean differs from source outcome')
    if expected == 'met' and not assessed['realized_observables']:
        raise ValueError('Complete motion lacks measured observables')
    return {'case_id': case_id, 'construction_sha256': entry['construction_sha256'],
            'fixture_kind': kind, 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True, 'actual_native_capture': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False, **assessed}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--tamper', action='store_true')
    parser.add_argument('--output', default='.runtime-work/c295149-release-motion-diagnostic')
    parser.add_argument('--case')
    parser.add_argument('--kind')
    args = parser.parse_args()
    if args.comparison == 'release_motion_diagnostic':
        print(json.dumps(audit_release_motion_diagnostic(args.output, tamper=args.tamper)))
    elif args.comparison == 'physical_outcome_diagnostic':
        print(json.dumps(audit_physical_outcomes(tamper=args.tamper)))
    elif args.comparison == 'physical_fixture':
        if not args.case or not args.kind:
            raise ValueError('Exact case and fixture kind required')
        result = physical_fixture(args.case, args.kind, tamper=args.tamper)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'case_id': args.case, 'kind': args.kind,
                          'status': 'passed', 'synthetic_fixture': True}))
    else:
        print(json.dumps(audit_exact(args.comparison, tamper=args.tamper)))
