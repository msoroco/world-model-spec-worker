"""Author the exact no-signal turn-lane primary and three physical fallbacks."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__bicycle_no_signal'
CASE = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__turn_lane_no_signal'
FOLDER = ROOT / 'cases/turn_lane_no_signal'
SOURCE_VIDEO_SHA = '4d5541f025afa64755261e4f4811e6b61617fd1cd22d0a62dc785fcf61a6d230'
REQUIREMENT = 'bicycle roadway turn without a signal from a source-reviewed designated turn-lane candidate'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def save(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, allow_nan=False) + '\n')


def runner(source):
    source = source.replace('from rider_route import control, select_left_turn',
        'from rider_route import control, select_left_turn\nfrom rider_turn_lane import capture_lane')
    source = source.replace('sinks = {}', 'sinks = {}\n    lane_rows = None')
    source = source.replace("bone_rows = (output / 'rider_arm_bones.jsonl').open('x')",
        "bone_rows = (output / 'rider_arm_bones.jsonl').open('x')\n        lane_rows = (output / 'lane_waypoint_readback.jsonl').open('x')")
    source = source.replace('frames = []', 'frames = []\n        frame_times = []')
    source = source.replace('frame_map.append(frame, time_s)',
        "lane_rows.write(json.dumps(capture_lane(world.get_map(), bicycle.get_transform().location, frame, time_s)) + '\\n')\n            frame_map.append(frame, time_s)")
    source = source.replace('frames.append(frame)', 'frames.append(frame)\n            frame_times.append(time_s)')
    marker = '        cameras.verify(frames)\n'
    review = '''        cameras.verify(frames)
        for sink in sinks.values():
            sink.close()
        sinks.clear()
        from hashlib import sha256
        video_sha = sha256((output / 'driver_reference.mkv').read_bytes()).hexdigest()
        (output / 'turn_lane_marking_review.jsonl').write_text(''.join(
            json.dumps({'frame': frame, 'time_s': time_s,
                        'source_video_sha256': video_sha,
                        'visible_turn_lane_designation': None}) + '\\n'
            for frame, time_s in zip(frames, frame_times)))
'''
    source = source.replace(marker, review)
    source = source.replace('if bone_rows is not None:\n            bone_rows.close()',
        'if bone_rows is not None:\n            bone_rows.close()\n        if lane_rows is not None:\n            lane_rows.close()')
    if 'capture_lane(world.get_map()' not in source or 'turn_lane_marking_review.jsonl' not in source:
        raise ValueError('Native turn-lane insertion failed')
    return source


def finalizer(source):
    marker = "if __name__ == '__main__':\n    main()"
    extension = '''from rider_turn_lane import measure as _lane_measure

def measure_turn_lane(attempt):
    return _lane_measure(attempt)

_base_analyze = analyze
def analyze(attempt):
    report = _base_analyze(attempt)
    observation = measure_turn_lane(attempt)
    report['measurements']['turn_lane_observation'] = {
        'method': 'measure_turn_lane', 'value': observation,
        'sources': observation['sources']}
    return report

_base_build_result = build_result
def build_result(attempt, report):
    result = _base_build_result(attempt, report)
    observation = report['measurements']['turn_lane_observation']['value']
    result['measured_values']['turn_lane_observation'] = observation
    root = Path(attempt)
    path = root / 'turn_lane_designation.jsonl'
    if path.exists():
        raise ValueError('Retain prior derived lane channel')
    reviews = [json.loads(line) for line in (root / 'turn_lane_marking_review.jsonl').read_text().splitlines() if line.strip()]
    path.write_text(''.join(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
        'value': int(row['visible_turn_lane_designation'] is True),
        'reviewed': row['visible_turn_lane_designation'] is not None}) + '\\n' for row in reviews))
    from hashlib import sha256
    result['recording_evidence'].append({'name': 'turn_lane_designation_visible',
        'unit': 'count', 'reference': 'turn_lane_designation.jsonl',
        'sha256': sha256(path.read_bytes()).hexdigest()})
    result['realized_observables']['turn_lane_designation_visible'] = {
        'unit': 'count', 'method': 'source-video review joined to original lane readback',
        'time_window': 'all original frames', 'statistic': 'visible designation frames',
        'reference': 'turn_lane_designation.jsonl',
        'value': len(observation['visible_designation_frames']),
        'sample_window_s': [reviews[0]['time_s'], reviews[-1]['time_s']]}
    result['physical_acceptance_claimed'] = False
    result['legal_acceptance_claimed'] = False
    return result

'''
    if marker not in source:
        raise ValueError('Finalizer marker missing')
    return source.replace(marker, extension + marker)


def finalizer_test(source):
    marker = '    for name, items in rows.items():\n'
    rows = '''    rows['lane_waypoint_readback.jsonl'] = [
        {'frame': i, 'time_s': i * .05, 'road_id': 1, 'lane_id': -1,
         'lane_type': 'Driving', 'is_junction': i > 1,
         'left_marking_type': 'Solid', 'right_marking_type': 'Broken',
         'designation_from_map': None} for i in range(4)]
    rows['turn_lane_marking_review.jsonl'] = [
        {'frame': i, 'time_s': i * .05, 'source_video_sha256': video_sha,
         'visible_turn_lane_designation': None} for i in range(4)]
'''
    if marker not in source:
        raise ValueError('Finalizer test fixture marker missing')
    return source.replace(marker, rows + marker)


def build_construction(source, output):
    value = json.loads(source.read_text())
    value = json.loads(json.dumps(value).replace(BASE, CASE))
    value['case_id'] = CASE
    value['recording_description']['channels'].append({
        'name': 'turn_lane_designation_visible', 'unit': 'count',
        'method': 'per-frame source-video review joined to Native lane waypoint',
        'sampling_rate_hz': 20, 'time_window': 'all original frames',
        'reference_frame': 'driver_reference video and original Native frame map',
        'uncertainty': 'map lane marking readback does not by itself prove a designated turn lane'})
    value['recording_description']['limitations'].append(
        'Black diagnostic video cannot confirm turn-lane designation; no legal exception is claimed.')
    files = {entry['path']: entry for entry in value['files']}
    for name in ('config.json', 'probe-config.json'):
        config = json.loads(files[name]['content'])
        config['lane_route_selector'] = 'designated_left_turn_lane_candidate'
        config['case']['recording_description'] = value['recording_description']
        files[name]['content'] = json.dumps(config, indent=2) + '\n'
    for name in ('native_rider_probe.py', 'runner.py'):
        files[name]['content'] = runner(files[name]['content'])
    files['rider_signal_finalizer.py']['content'] = finalizer(files['rider_signal_finalizer.py']['content'])
    files['tests/test_rider_signal_finalizer.py']['content'] = finalizer_test(
        files['tests/test_rider_signal_finalizer.py']['content'])
    value['files'].append({'path': 'rider_turn_lane.py', 'content': (ROOT / 'rider_turn_lane.py').read_text()})
    save(output, value)


def main():
    FOLDER.mkdir(exist_ok=True)
    build_construction(ROOT / 'cases/bicycle_no_signal/construction.json', FOLDER / 'construction.json')
    for number in (1, 2, 3):
        build_construction(ROOT / f'cases/bicycle_no_signal/fallback{number}-construction.json',
                           FOLDER / f'fallback{number}-construction.json')
    diagnostic = json.loads((ROOT / 'cases/bicycle_no_signal/diagnostic-input.json').read_text())
    diagnostic = json.loads(json.dumps(diagnostic).replace(BASE, CASE))
    frames = [json.loads(line) for line in diagnostic['files']['video_frames.jsonl'].splitlines() if line.strip()]
    lanes = [{'frame': frame['carla_frame'], 'time_s': frame['time_s'],
              'road_id': 1, 'lane_id': -1, 'lane_type': 'Driving',
              'is_junction': index >= 5, 'left_marking_type': 'Solid',
              'right_marking_type': 'Broken', 'designation_from_map': None}
             for index, frame in enumerate(frames)]
    reviews = [{'frame': frame['carla_frame'], 'time_s': frame['time_s'],
                'source_video_sha256': SOURCE_VIDEO_SHA,
                'visible_turn_lane_designation': None} for frame in frames]
    diagnostic['files']['lane_waypoint_readback.jsonl'] = ''.join(json.dumps(row)+'\n' for row in lanes)
    diagnostic['files']['turn_lane_marking_review.jsonl'] = ''.join(json.dumps(row)+'\n' for row in reviews)
    save(FOLDER / 'diagnostic-input.json', diagnostic, compact=True)
    recipe_source = str((FOLDER / 'diagnostic-input.json').relative_to(REPO))
    save(FOLDER / 'diagnostic-recipe.json', {'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-input.json', 'source': recipe_source,
                     'sha256': sha(FOLDER / 'diagnostic-input.json')}],
        'generator': {'source': recipe_source, 'sha256': sha(FOLDER / 'diagnostic-input.json')}})
    contract = json.loads((ROOT / 'cases/bicycle_no_signal/measurement-contract.json').read_text())
    contract = json.loads(json.dumps(contract).replace(BASE, CASE))
    contract['requirements'][0].update({'disposition_index': 5,
        'requirement': REQUIREMENT, 'output_key': 'turn_lane_observation',
        'method': 'measure_turn_lane',
        'inputs': ['video_frames.jsonl', 'lane_waypoint_readback.jsonl',
                   'turn_lane_marking_review.jsonl', 'driver_reference.mkv']})
    contract['negative'] = {'remove': ['lane_waypoint_readback.jsonl'],
                            'error_contains': 'Missing required source: lane_waypoint_readback.jsonl'}
    save(FOLDER / 'measurement-contract.json', contract)
    manifest = json.loads((ROOT / 'no-signal-manifest.json').read_text())
    entry = manifest['cases'][0]
    entry['case_id'] = CASE
    entry['construction'] = 'cases/turn_lane_no_signal/construction.json'
    entry['construction_sha256'] = sha(FOLDER / 'construction.json')
    entry['measurement_contract'] = 'cases/turn_lane_no_signal/measurement-contract.json'
    entry['fixture_recipe'] = str((FOLDER / 'diagnostic-recipe.json').relative_to(REPO))
    entry.pop('physical_preparation', None)
    for number, candidate in enumerate(entry['candidates'], 1):
        candidate['construction'] = f'cases/turn_lane_no_signal/fallback{number}-construction.json'
        candidate['construction_sha256'] = sha(FOLDER / f'fallback{number}-construction.json')
        candidate.pop('offline', None)
        candidate.pop('compatibility', None)
    save(ROOT / 'turn-lane-manifest.json', manifest)
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if len(plan['requirement_dispositions']) == 5:
        plan['requirement_dispositions'].append({'requirement': REQUIREMENT,
            'source': 'inputs/heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator/assignment.json',
            'status': 'selected_required', 'case_ids': [CASE],
            'reason': 'turn-lane no-signal software diagnostic; designation and legal exception remain unverified',
            'evidence_or_gap': 'Black source videos and unknown designation review do not establish a designated turn lane.'})
    if len(plan['requirement_dispositions']) != 6:
        raise ValueError('Unexpected rider disposition count')
    next(item for item in plan['cases'] if item['case_id'] == CASE)['construction_status'] = 'primary_and_three_fallbacks_authored_cpu_proofs_pending_physical_unverified'
    save(plan_path, plan)
    proposal_path = ROOT / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    proposal['cases'] = [case for case in proposal['cases'] if case['case_id'] != CASE]
    case = json.loads(json.dumps(next(c for c in proposal['cases'] if c['case_id'] == BASE)))
    case['case_id'] = CASE
    case['rationale'] = 'No-signal turn-lane source-join diagnostic; actual designation and legal exception remain open'
    case['variable_assignments']['lane_route_selector'] = {'kind': 'controller', 'value': 'designated_left_turn_lane_candidate'}
    case['recording_description'] = json.loads((FOLDER / 'construction.json').read_text())['recording_description']
    case['paired_probe_id'] = 'turn_lane_exception'
    case['deliberate_differences'] = ['lane_route_selector']
    case['probe'] = {'primary_variable': 'lane_route_selector',
                     'comparison_or_standard': 'no-signal generic lane versus designated-turn-lane candidate',
                     'target_value_or_branch': 'turn-lane candidate'}
    proposal['cases'].append(case)
    save(proposal_path, proposal)
    print(CASE, entry['construction_sha256'])


if __name__ == '__main__':
    main()
