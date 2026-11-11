"""Author the exact both-hands no-signal primary and three fallbacks."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__bicycle_no_signal'
CASE = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__both_hands_no_signal'
FOLDER = ROOT / 'cases/both_hands_no_signal'
VIDEO_SHA = '4d5541f025afa64755261e4f4811e6b61617fd1cd22d0a62dc785fcf61a6d230'
REQUIREMENT = 'bicycle roadway turn without a signal under a source-reviewed two-hand control-demand candidate'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def save(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, allow_nan=False) + '\n')


def runner(source):
    source = source.replace('from rider_route import control, select_left_turn',
        'from rider_route import control, select_left_turn\nfrom rider_hand_control import capture_hands, capture_stability')
    source = source.replace('sinks = {}', 'sinks = {}\n    hand_rows = stability_rows = None')
    source = source.replace("bone_rows = (output / 'rider_arm_bones.jsonl').open('x')",
        "bone_rows = (output / 'rider_arm_bones.jsonl').open('x')\n        hand_rows = (output / 'hand_contact_readback.jsonl').open('x')\n        stability_rows = (output / 'control_stability.jsonl').open('x')")
    source = source.replace('frames = []', 'frames = []\n        frame_times = []')
    original = '            bicycle.apply_control(carla.VehicleControl(**_control(bicycle, target)))'
    replacement = '''            command = _control(bicycle, target)
            if 28 <= index <= 40:
                command['steer'] = max(-1., min(1., command['steer'] + (.03 if index % 2 else -.03)))
            bicycle.apply_control(carla.VehicleControl(**command))'''
    if original not in source:
        raise ValueError('Native rider control insertion missing')
    source = source.replace(original, replacement)
    source = source.replace('frame_map.append(frame, time_s)',
        "hand_rows.write(json.dumps(capture_hands(rider, frame, time_s)) + '\\n')\n            stability_rows.write(json.dumps(capture_stability(trace, frame, time_s, command)) + '\\n')\n            frame_map.append(frame, time_s)")
    source = source.replace('frames.append(frame)', 'frames.append(frame)\n            frame_times.append(time_s)')
    marker = '        cameras.verify(frames)\n'
    review = '''        cameras.verify(frames)
        for sink in sinks.values():
            sink.close()
        sinks.clear()
        from hashlib import sha256
        video_sha = sha256((output / 'driver_reference.mkv').read_bytes()).hexdigest()
        (output / 'hand_contact_review.jsonl').write_text(''.join(
            json.dumps({'frame': frame, 'time_s': time_s,
                        'source_video_sha256': video_sha,
                        'left_hand_contact': None, 'right_hand_contact': None}) + '\\n'
            for frame, time_s in zip(frames, frame_times)))
'''
    source = source.replace(marker, review)
    source = source.replace('if bone_rows is not None:\n            bone_rows.close()',
        'if bone_rows is not None:\n            bone_rows.close()\n        if hand_rows is not None:\n            hand_rows.close()\n        if stability_rows is not None:\n            stability_rows.close()')
    if 'capture_hands(rider' not in source or 'hand_contact_review.jsonl' not in source:
        raise ValueError('Native hand-control insertion failed')
    return source


def finalizer(source):
    marker = "if __name__ == '__main__':\n    main()"
    extension = '''from rider_hand_control import measure as _hand_measure

def measure_both_hands(attempt):
    return _hand_measure(attempt)

_base_analyze = analyze
def analyze(attempt):
    report = _base_analyze(attempt)
    observation = measure_both_hands(attempt)
    report['measurements']['both_hands_observation'] = {
        'method': 'measure_both_hands', 'value': observation,
        'sources': observation['sources']}
    return report

_base_build_result = build_result
def build_result(attempt, report):
    result = _base_build_result(attempt, report)
    observation = report['measurements']['both_hands_observation']['value']
    result['measured_values']['both_hands_observation'] = observation
    root = Path(attempt)
    path = root / 'two_hand_contact.jsonl'
    if path.exists():
        raise ValueError('Retain prior derived hand-contact channel')
    reviews = [json.loads(line) for line in (root / 'hand_contact_review.jsonl').read_text().splitlines() if line.strip()]
    path.write_text(''.join(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
        'value': int(row['left_hand_contact'] is True and row['right_hand_contact'] is True),
        'reviewed': row['left_hand_contact'] is not None and row['right_hand_contact'] is not None}) + '\\n' for row in reviews))
    from hashlib import sha256
    result['recording_evidence'].append({'name': 'two_hand_contact_observed',
        'unit': 'count', 'reference': 'two_hand_contact.jsonl',
        'sha256': sha256(path.read_bytes()).hexdigest()})
    result['realized_observables']['two_hand_contact_observed'] = {
        'unit': 'count', 'method': 'source-video hand-contact review joined to Native readback',
        'time_window': 'all original frames', 'statistic': 'reviewed two-hand contact frames',
        'reference': 'two_hand_contact.jsonl',
        'value': len(observation['both_hands_visible_contact_frames']),
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
    rows = '''    rows['hand_contact_readback.jsonl'] = [
        {'frame': i, 'time_s': i * .05, 'rider_id': 'rider-1',
         'hand_bone_readback': {'crl_hand__L': None, 'crl_hand__R': None},
         'physical_handlebar_contact_verified': None} for i in range(4)]
    rows['control_stability.jsonl'] = [
        {'frame': i, 'time_s': i * .05, 'wheel_steer_angle_deg': 0,
         'speed_mps': 1, 'accel_longitudinal_mps2': 0,
         'commanded_steer': .03, 'control_stability_judgment': None} for i in range(4)]
    rows['hand_contact_review.jsonl'] = [
        {'frame': i, 'time_s': i * .05, 'source_video_sha256': video_sha,
         'left_hand_contact': None, 'right_hand_contact': None} for i in range(4)]
'''
    if marker not in source:
        raise ValueError('Finalizer test fixture marker missing')
    return source.replace(marker, rows + marker)


def build_construction(source, output):
    value = json.loads(source.read_text())
    value = json.loads(json.dumps(value).replace(BASE, CASE))
    value['case_id'] = CASE
    value['recording_description']['channels'].append({
        'name': 'two_hand_contact_observed', 'unit': 'count',
        'method': 'per-frame source-video review joined to hand-bone and control readback',
        'sampling_rate_hz': 20, 'time_window': 'all original frames',
        'reference_frame': 'driver_reference video and original Native frame map',
        'uncertainty': 'bone pose and command do not establish physical contact or safety necessity'})
    value['recording_description']['limitations'].append(
        'Black diagnostic video cannot confirm either hand on the handlebar or that safe operation requires both hands.')
    files = {entry['path']: entry for entry in value['files']}
    for name in ('config.json', 'probe-config.json'):
        config = json.loads(files[name]['content'])
        config['both_hands_demand_mode'] = 'steering_perturbation_28_to_40'
        config['case']['recording_description'] = value['recording_description']
        files[name]['content'] = json.dumps(config, indent=2) + '\n'
    for name in ('native_rider_probe.py', 'runner.py'):
        files[name]['content'] = runner(files[name]['content'])
    files['rider_signal_finalizer.py']['content'] = finalizer(files['rider_signal_finalizer.py']['content'])
    files['tests/test_rider_signal_finalizer.py']['content'] = finalizer_test(
        files['tests/test_rider_signal_finalizer.py']['content'])
    value['files'].append({'path': 'rider_hand_control.py', 'content': (ROOT / 'rider_hand_control.py').read_text()})
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
    rider_id = json.loads(diagnostic['files']['rider_context.json'])['rider_id']
    bones = [{'frame': frame['carla_frame'], 'time_s': frame['time_s'],
              'rider_id': rider_id, 'hand_bone_readback': {'crl_hand__L': None, 'crl_hand__R': None},
              'physical_handlebar_contact_verified': None} for frame in frames]
    controls = [{'frame': frame['carla_frame'], 'time_s': frame['time_s'],
                 'wheel_steer_angle_deg': 0, 'speed_mps': 1, 'accel_longitudinal_mps2': 0,
                 'commanded_steer': (.03 if 3 <= i <= 6 and i % 2 else -.03 if 3 <= i <= 6 else 0),
                 'control_stability_judgment': None} for i, frame in enumerate(frames)]
    reviews = [{'frame': frame['carla_frame'], 'time_s': frame['time_s'],
                'source_video_sha256': VIDEO_SHA, 'left_hand_contact': None,
                'right_hand_contact': None} for frame in frames]
    diagnostic['files']['hand_contact_readback.jsonl'] = ''.join(json.dumps(row)+'\n' for row in bones)
    diagnostic['files']['control_stability.jsonl'] = ''.join(json.dumps(row)+'\n' for row in controls)
    diagnostic['files']['hand_contact_review.jsonl'] = ''.join(json.dumps(row)+'\n' for row in reviews)
    save(FOLDER / 'diagnostic-input.json', diagnostic, compact=True)
    recipe_source = str((FOLDER / 'diagnostic-input.json').relative_to(REPO))
    save(FOLDER / 'diagnostic-recipe.json', {'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-input.json', 'source': recipe_source,
                     'sha256': sha(FOLDER / 'diagnostic-input.json')}],
        'generator': {'source': recipe_source, 'sha256': sha(FOLDER / 'diagnostic-input.json')}})
    contract = json.loads((ROOT / 'cases/bicycle_no_signal/measurement-contract.json').read_text())
    contract = json.loads(json.dumps(contract).replace(BASE, CASE))
    contract['requirements'][0].update({'disposition_index': 6,
        'requirement': REQUIREMENT, 'output_key': 'both_hands_observation',
        'method': 'measure_both_hands',
        'inputs': ['video_frames.jsonl', 'rider_context.json', 'hand_contact_readback.jsonl',
                   'control_stability.jsonl', 'hand_contact_review.jsonl', 'driver_reference.mkv']})
    contract['negative'] = {'remove': ['hand_contact_readback.jsonl'],
                            'error_contains': 'Missing required source: hand_contact_readback.jsonl'}
    save(FOLDER / 'measurement-contract.json', contract)
    manifest = json.loads((ROOT / 'no-signal-manifest.json').read_text())
    entry = manifest['cases'][0]
    entry['case_id'] = CASE
    entry['construction'] = 'cases/both_hands_no_signal/construction.json'
    entry['construction_sha256'] = sha(FOLDER / 'construction.json')
    entry['measurement_contract'] = 'cases/both_hands_no_signal/measurement-contract.json'
    entry['fixture_recipe'] = str((FOLDER / 'diagnostic-recipe.json').relative_to(REPO))
    entry.pop('physical_preparation', None)
    for number, candidate in enumerate(entry['candidates'], 1):
        candidate['construction'] = f'cases/both_hands_no_signal/fallback{number}-construction.json'
        candidate['construction_sha256'] = sha(FOLDER / f'fallback{number}-construction.json')
        candidate.pop('offline', None)
        candidate.pop('compatibility', None)
    save(ROOT / 'both-hands-manifest.json', manifest)
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if len(plan['requirement_dispositions']) == 6:
        plan['requirement_dispositions'].append({'requirement': REQUIREMENT,
            'source': 'inputs/heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator/assignment.json',
            'status': 'selected_required', 'case_ids': [CASE],
            'reason': 'two-hand control-demand software diagnostic; physical necessity and legal exception unresolved',
            'evidence_or_gap': 'Bone/control readback and black pixels cannot prove hand contact or safe-operation necessity.'})
    if len(plan['requirement_dispositions']) != 7:
        raise ValueError('Unexpected rider disposition count')
    next(item for item in plan['cases'] if item['case_id'] == CASE)['construction_status'] = 'primary_and_three_fallbacks_authored_cpu_proofs_pending_physical_unverified'
    save(plan_path, plan)
    proposal_path = ROOT / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    proposal['cases'] = [case for case in proposal['cases'] if case['case_id'] != CASE]
    case = json.loads(json.dumps(next(c for c in proposal['cases'] if c['case_id'] == BASE)))
    case['case_id'] = CASE
    case['rationale'] = 'No-signal two-hand control-demand source-join diagnostic; safety necessity and exception remain open'
    case['variable_assignments']['both_hands_demand_mode'] = {'kind': 'controller', 'value': 'steering_perturbation_28_to_40'}
    case['recording_description'] = json.loads((FOLDER / 'construction.json').read_text())['recording_description']
    case['paired_probe_id'] = 'both_hands_exception'
    case['deliberate_differences'] = ['both_hands_demand_mode']
    case['probe'] = {'primary_variable': 'both_hands_demand_mode',
                     'comparison_or_standard': 'no-signal generic turn versus two-hand control-demand candidate',
                     'target_value_or_branch': 'two-hand demand candidate'}
    proposal['cases'].append(case)
    save(proposal_path, proposal)
    print(CASE, entry['construction_sha256'])


if __name__ == '__main__':
    main()
