"""Author two exact rider clearance constructions and diagnostic source recipes."""
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__bicycle_signal_once'
PREFIX = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__'
SAFETY_REQUIREMENTS = {
    'safety_wide': 'signaled bicycle roadway turn with a source-measured wide participant clearance',
    'safety_narrow': 'signaled bicycle roadway turn with a source-measured narrow participant clearance',
}


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def adjust_runner(source, offset):
    source = source.replace('from rider_route import control, select_left_turn',
        'from rider_route import control, select_left_turn\nfrom rider_participant import Recorder, spawn')
    source = source.replace('actors.append(bicycle)\n',
        f'actors.append(bicycle)\n        participant = spawn(world, carla, library, route, {offset}.0)\n        actors.append(participant)\n', 1)
    source = source.replace("bone_rows = (output / 'rider_arm_bones.jsonl').open('x')",
        "bone_rows = (output / 'rider_arm_bones.jsonl').open('x')\n        participant_recorder = Recorder(output)")
    source = source.replace('frame_map.append(frame, time_s)',
        'participant_recorder.capture(frame, time_s, trace, participant)\n            frame_map.append(frame, time_s)')
    source = source.replace('if bone_rows is not None:\n            bone_rows.close()',
        'if bone_rows is not None:\n            bone_rows.close()\n        if participant_recorder is not None:\n            participant_recorder.close()')
    source = source.replace('sinks = {}', 'sinks = {}\n    participant_recorder = None')
    for token in ('from rider_participant import Recorder, spawn', 'participant_recorder.capture',
                  'participant_recorder.close()'):
        if token not in source:
            raise ValueError('Native participant construction insertion failed: ' + token)
    return source


def adjust_finalizer(source):
    before = "if __name__ == '__main__':\n    main()"
    extension = '''from rider_clearance_measurement import measure as _clearance_measure

def measure_rider_clearance(attempt):
    return _clearance_measure(attempt)

_signal_analyze = analyze
def analyze(attempt):
    report = _signal_analyze(attempt)
    observed = measure_rider_clearance(attempt)
    report['measurements']['rider_clearance_observation'] = {
        'method': 'measure_rider_clearance', 'value': observed,
        'sources': observed['sources']}
    return report

_signal_build_result = build_result
def build_result(attempt, report):
    result = _signal_build_result(attempt, report)
    result['measured_values']['rider_clearance_observation'] = report['measurements']['rider_clearance_observation']['value']
    result['realized_observables']['participant_center_clearance'] = {
        'unit': 'm', 'method': 'joined original rider and participant trajectories',
        'time_window': 'all original frames', 'statistic': 'minimum',
        'reference': 'clearance_samples.jsonl',
        'value': result['measured_values']['rider_clearance_observation']['minimum_center_distance_m'],
        'sample_window_s': [0, 10]}
    result['physical_acceptance_claimed'] = False
    result['legal_acceptance_claimed'] = False
    return result

'''
    if before not in source:
        raise ValueError('Finalizer main marker missing')
    return source.replace(before, extension + before)


def adjust_finalizer_test(source, offset):
    source = source.replace("'trace.jsonl': [{'frame': i, 'time_s': i * .05} for i in range(4)]",
        "'trace.jsonl': [{'frame': i, 'time_s': i * .05, 'position_m': [float(i), 0.0, 0.0]} for i in range(4)]")
    marker = '    for name, items in rows.items():\n'
    addition = ("    rows['participant_motion.jsonl'] = [{'frame': i, 'time_s': i * .05,\n"
                f"        'actor_id': 'other-1', 'position_m': [float(i), {offset}.0, 0.0]}} for i in range(4)]\n"
                "    rows['clearance_samples.jsonl'] = [{'frame': i, 'time_s': i * .05,\n"
                f"        'participant_actor_id': 'other-1', 'center_distance_m': {offset}.0}} for i in range(4)]\n")
    if marker not in source or "'position_m': [float(i), 0.0, 0.0]" not in source:
        raise ValueError('Clearance offline test fixture insertion failed')
    return source.replace(marker, addition + marker)


def build_one(slug, offset):
    folder = ROOT / 'cases' / slug
    folder.mkdir(exist_ok=True)
    case_id = PREFIX + slug
    construction = json.loads((ROOT / 'first-construction.json').read_text())
    construction = json.loads(json.dumps(construction).replace(BASE, case_id))
    construction['case_id'] = case_id
    construction['recording_description']['limitations'].append(
        'Participant clearance is a synthetic source-join diagnostic; black video does not confirm the participant.')
    files = {entry['path']: entry for entry in construction['files']}
    for name in ('probe-config.json', 'config.json'):
        config = json.loads(files[name]['content'])
        config['clearance_band'] = slug
        config['participant_lateral_offset_m'] = float(offset)
        config['case']['recording_description'] = construction['recording_description']
        files[name]['content'] = json.dumps(config, indent=2) + '\n'
    for name in ('native_rider_probe.py', 'runner.py'):
        files[name]['content'] = adjust_runner(files[name]['content'], offset)
    files['rider_signal_finalizer.py']['content'] = adjust_finalizer(files['rider_signal_finalizer.py']['content'])
    files['tests/test_rider_signal_finalizer.py']['content'] = adjust_finalizer_test(
        files['tests/test_rider_signal_finalizer.py']['content'], offset)
    for name in ('rider_participant.py', 'rider_clearance_measurement.py'):
        construction['files'].append({'path': name, 'content': (ROOT / name).read_text()})
    save(folder / 'construction.json', construction)

    diagnostic = json.loads((ROOT / 'diagnostic-input.json').read_text())
    diagnostic = json.loads(json.dumps(diagnostic).replace(BASE, case_id))
    trace = [json.loads(line) for line in diagnostic['files']['trace.jsonl'].splitlines() if line]
    motion, clearance = [], []
    for row in trace:
        rider = row['position_m']
        other = [float(rider[0]), float(rider[1]) + offset, float(rider[2])]
        distance = hypot(float(rider[0])-other[0], float(rider[1])-other[1])
        motion.append({'frame': row['frame'], 'time_s': row['time_s'],
                       'actor_id': 'diagnostic-participant-1', 'position_m': other})
        clearance.append({'frame': row['frame'], 'time_s': row['time_s'],
                          'participant_actor_id': 'diagnostic-participant-1',
                          'center_distance_m': distance})
    diagnostic['files']['participant_motion.jsonl'] = ''.join(json.dumps(r)+'\n' for r in motion)
    diagnostic['files']['clearance_samples.jsonl'] = ''.join(json.dumps(r)+'\n' for r in clearance)
    (folder / 'diagnostic-input.json').write_text(json.dumps(diagnostic, separators=(',', ':'), allow_nan=False) + '\n')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': str((folder / 'diagnostic-input.json').relative_to(REPO)),
                           'sha256': digest(folder / 'diagnostic-input.json')}],
              'generator': {'source': str((folder / 'diagnostic-input.json').relative_to(REPO)),
                            'sha256': digest(folder / 'diagnostic-input.json')}}
    save(folder / 'diagnostic-recipe.json', recipe)
    contract = json.loads((ROOT / 'first-measurement-contract.json').read_text())
    contract = json.loads(json.dumps(contract).replace(BASE, case_id))
    contract['requirements'][0].update({
        'disposition_index': 3 if slug == 'safety_wide' else 4,
        'requirement': SAFETY_REQUIREMENTS[slug],
        'output_key': 'rider_clearance_observation', 'method': 'measure_rider_clearance',
        'inputs': ['video_frames.jsonl', 'trace.jsonl', 'participant_motion.jsonl',
                   'clearance_samples.jsonl']})
    contract['negative'] = {'remove': ['participant_motion.jsonl'],
                            'error_contains': 'Missing required source: participant_motion.jsonl'}
    save(folder / 'measurement-contract.json', contract)
    manifest = json.loads((ROOT / 'first-execution-manifest.json').read_text())
    entry = manifest['cases'][0]
    entry['case_id'] = case_id
    entry['construction'] = 'construction.json'
    entry['construction_sha256'] = digest(folder / 'construction.json')
    entry['measurement_contract'] = 'measurement-contract.json'
    entry['fixture_recipe'] = str((folder / 'diagnostic-recipe.json').relative_to(REPO))
    entry.pop('physical_preparation', None)
    entry.pop('candidates', None)
    save(folder / 'manifest.json', manifest)
    entry['construction'] = str((folder / 'construction.json').relative_to(ROOT))
    entry['measurement_contract'] = str((folder / 'measurement-contract.json').relative_to(ROOT))
    save(ROOT / (slug.replace('_', '-') + '-manifest.json'), manifest)
    print(slug, entry['construction_sha256'])


if __name__ == '__main__':
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    dispositions = plan['requirement_dispositions']
    if len(dispositions) not in (3, 5):
        raise ValueError('Unexpected rider requirement disposition count')
    if len(dispositions) == 3:
        for slug in ('safety_wide', 'safety_narrow'):
            dispositions.append({'requirement': SAFETY_REQUIREMENTS[slug],
                'source': 'inputs/heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator/assignment.json',
                'status': 'selected_required', 'case_ids': [PREFIX + slug],
                'reason': 'exact CPU source-join diagnostic; physical clearance and legal safety remain unverified',
                'evidence_or_gap': 'No accepted Native recording; synthetic participant trajectory and black videos only test measurement plumbing.'})
        save(plan_path, plan)
    build_one('safety_wide', 8)
    build_one('safety_narrow', 3)
    proposal_path = ROOT / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    proposal['cases'] = [case for case in proposal['cases']
                         if case['case_id'] not in (PREFIX + 'safety_wide', PREFIX + 'safety_narrow')]
    for slug, offset in (('safety_wide', 8), ('safety_narrow', 3)):
        case = json.loads(json.dumps(proposal['cases'][0]))
        case['case_id'] = PREFIX + slug
        case['rationale'] = 'Controlled participant-clearance source join diagnostic; physical and legal decisions remain open'
        case['variable_assignments']['participant_lateral_offset_m'] = {
            'kind': 'controller', 'value': float(offset)}
        case['paired_probe_id'] = 'reasonable_safety_clearance'
        case['deliberate_differences'] = ['participant_lateral_offset_m']
        case['epsilon_used'] = 5
        case['probe'] = {'primary_variable': 'participant_lateral_offset_m',
                         'comparison_or_standard': 'wide versus narrow participant clearance',
                         'target_value_or_branch': slug}
        proposal['cases'].append(case)
    save(proposal_path, proposal)
