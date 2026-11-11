"""Bind first exact officer-indication source contract and marked CPU fixture."""

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE_ID = ROOT.name + '__stop_responds'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, value, *, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')


def main():
    assignment = REPO / 'inputs' / ROOT.name / 'assignment.json'
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['selected_branch'] = json.loads(assignment.read_text())['branches'][0]['branch']
    plan['requirement_dispositions'] = [{
        'requirement': 'Officer lawful-duty direction addressed to the subject, followed by observed response; lawfulness and willfulness reserved for review',
        'source': str(assignment.relative_to(REPO)),
        'status': 'selected_required',
        'case_ids': [row['case_id'] for row in plan['cases']],
        'evidence_or_gap': 'Four exact indication/response contrasts selected; synthetic original-source diagnostics do not establish officer duty, order lawfulness or willfulness.'}]
    write(plan_path, plan)
    transfer = REPO / 'work/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/diagnostic-person_3mps.json'
    diagnostic = json.loads(transfer.read_text())
    files = diagnostic['files']
    for name in ('participant_footprints.jsonl', 'ego_motion.jsonl',
                 'alley_context.json', 'diagnostic-alley-polygon.json'):
        files.pop(name, None)
    files['fixture-provenance.json'] = json.dumps({
        'provenance_kind': 'synthetic_fixture',
        'scope': 'CPU diagnostic graph/video transfer plus newly authored C10365 officer/subject rows; no Native officer or lawful order evidence',
        'source_case': 'C10364 diagnostic-person_3mps.json',
        'source_sha256': digest(transfer)}) + '\n'
    mapping = [json.loads(line) for line in files['video_frames.jsonl'].splitlines() if line.strip()]
    trace = [json.loads(line) for line in files['trace.jsonl'].splitlines() if line.strip()]
    if len(mapping) != 9 or len(trace) != 9:
        raise ValueError('Transferred diagnostic frame count differs')
    indication = mapping[3]['carla_frame']
    files['officer_context.json'] = json.dumps({
        'actor_role': 'motor_vehicle_driver', 'officer_role': 'police_officer',
        'officer_id': 'fixture-officer', 'subject_id': 'fixture-subject',
        'duty_source': 'synthetic diagnostic source context; independent Native review required',
        'lawfulness_source': 'synthetic diagnostic source context; legal review required'}) + '\n'
    files['officer_direction.json'] = json.dumps({
        'frame': indication, 'officer_id': 'fixture-officer',
        'subject_id': 'fixture-subject', 'command': 'stop',
        'indication_source': 'marked synthetic original four-view arm cue'}) + '\n'
    rows = []
    for index, (frame, state) in enumerate(zip(mapping, trace)):
        if frame['carla_frame'] != state['frame'] or frame['time_s'] != state['time_s']:
            raise ValueError('Diagnostic original trace/frame-map differs')
        rows.append({'frame': state['frame'], 'time_s': state['time_s'],
                     'subject_id': 'fixture-subject',
                     'speed_mps': 2.0 if index <= 3 else max(0.0, 1.0 - (index-4)*.5),
                     'position_m': [float(index), 0, 0]})
    files['subject_motion.json'] = json.dumps({'frames': rows}) + '\n'
    files['subject_motion_history.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
    fixture = ROOT / 'diagnostic-stop_responds.json'
    write(fixture, diagnostic, compact=True)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': str(fixture.relative_to(REPO)),
                           'sha256': digest(fixture)}],
              'generator': {'source': str(fixture.relative_to(REPO)),
                            'sha256': digest(fixture)}}
    recipe_path = ROOT / 'diagnostic-recipe-stop_responds.json'
    write(recipe_path, recipe)
    contract = {'format': 'worker-measurement-contract', 'case_id': CASE_ID,
                'requirements': [{'disposition_index': 0,
                    'requirement': plan['requirement_dispositions'][0]['requirement'],
                    'source': str(assignment.relative_to(REPO)),
                    'output_key': 'officer_response', 'method': 'measure_officer',
                    'value_type': 'object', 'kind': 'measured',
                    'inputs': ['officer_context.json', 'officer_direction.json',
                               'subject_motion.json', 'subject_motion_history.jsonl',
                               'video_frames.jsonl', 'trace.jsonl']}],
                'negative': {'remove': ['officer_direction.json'],
                             'error_contains': 'Missing required source: officer_direction.json'}}
    contract_path = ROOT / 'measurement-contract-stop_responds.json'
    write(contract_path, contract)
    selected = json.loads((ROOT / 'construction-probe-manifest.json').read_text())['cases'][0]
    manifest = {'format': 'worker-compatibility-manifest', 'assignment_id': ROOT.name,
                'runtime_manifest_sha256': digest(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': [{**selected, 'kind': 'delivery',
                    'measurement_contract': str(contract_path.relative_to(ROOT)),
                    'measurement_procedure': {'entrypoint': 'officer_finalizer.py'},
                    'fixture_recipe': str(recipe_path.relative_to(REPO)),
                    'acquisition': {
                        'subject_speed_mps': {'entrypoint': 'officer_finalizer.py',
                            'method': 'post-indication original subject velocity sampled at each joined frame',
                            'evidence': 'subject_motion_history.jsonl and original frame map'},
                        'officer_direction': {'entrypoint': 'officer_finalizer.py',
                            'method': 'timed officer pose event joined to original subject motion',
                            'evidence': 'officer_direction.json, officer_context.json and video_frames.jsonl'}}}]}
    write(ROOT / 'probe-compatibility-manifest.json', manifest)
    print('Bound first exact C10365 source-shaped diagnostic and measurement contract')


if __name__ == '__main__':
    main()
