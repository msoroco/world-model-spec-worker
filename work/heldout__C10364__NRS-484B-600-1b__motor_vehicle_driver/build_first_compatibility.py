"""Bind a marked synthetic first-case alley fixture and measurement contract."""

from hashlib import sha256
import json
from pathlib import Path


root = Path(__file__).resolve().parent
repo = root.parents[1]
aid = root.name
case_id = aid + '__person_3mps'
read = lambda path: json.loads(path.read_text())
write = lambda path, value: path.write_text(json.dumps(value, indent=2) + '\n')
digest = lambda path: sha256(path.read_bytes()).hexdigest()
assignment_path = repo / 'inputs' / aid / 'assignment.json'
assignment = read(assignment_path)
plan_path = root / 'case-plan.json'
plan = read(plan_path)
plan['selected_branch'] = assignment['branches'][0]['branch']
plan['requirement_dispositions'] = [{
    'requirement': 'Driving speed in continuous alley person or property exposure, with endangerment left to review',
    'source': str(assignment_path.relative_to(repo)),
    'status': 'selected_required',
    'case_ids': [case['case_id'] for case in plan['cases']],
    'evidence_or_gap': 'Six exact engineering contrasts planned; diagnostic originals test measurement only; Native physical and legal acceptance remain unverified.'}]
write(plan_path, plan)

source = read(repo / 'work' / 'heldout__C136539__NRS-484B-600-1b__motor_vehicle_driver' / 'diagnostic-slow.json')
source['files']['fixture-provenance.json'] = json.dumps({
    'provenance_kind': 'synthetic_fixture',
    'scope': 'CPU diagnostic graph/video transfer plus newly authored C10364 participant and motion rows; no Native alley evidence',
    'source_case': 'C136539 diagnostic-slow.json',
    'source_sha256': digest(repo / 'work' / 'heldout__C136539__NRS-484B-600-1b__motor_vehicle_driver' / 'diagnostic-slow.json')}) + '\n'
source['files'].pop('exposed_actor_footprints.jsonl', None)
trace = [json.loads(line) for line in source['files']['trace.jsonl'].splitlines() if line.strip()]
mapping = [json.loads(line) for line in source['files']['video_frames.jsonl'].splitlines() if line.strip()]
assert len(trace) == len(mapping) == 9

def box(x, y, half_x=.4, half_y=.25):
    return [[x-half_x,y-half_y], [x+half_x,y-half_y],
            [x+half_x,y+half_y], [x-half_x,y+half_y]]

footprints = []
motion = []
for i, (state, frame) in enumerate(zip(trace, mapping)):
    position = state['position']
    x, y = position['x'], position['y']
    assert state['frame'] == frame['carla_frame'] and state['time_s'] == frame['time_s']
    footprints.append({'frame': state['frame'], 'time_s': state['time_s'],
        'ego_id': 205, 'pedestrian_id': 305, 'property_id': 405,
        'ego_corners': box(x,y,2.4,.9),
        'pedestrian_corners': box(110,3.15,.3,.3),
        'property_corners': box(115,-3.15,.4,.4)})
    velocity = state.get('velocity_mps')
    if not isinstance(velocity, list):
        velocity = [0.5, 0.0]
    motion.append({'frame': state['frame'], 'time_s': state['time_s'],
                   'ego_id': 205, 'velocity_xy': list(velocity[:2]),
                   'acceleration_xy': [-.5,0.0], 'forward_xy': [1,0]})
source['files']['participant_footprints.jsonl'] = ''.join(json.dumps(row) + '\n' for row in footprints)
source['files']['ego_motion.jsonl'] = ''.join(json.dumps(row) + '\n' for row in motion)
fixture = root / 'diagnostic-person_3mps.json'
fixture.write_text(json.dumps(source, separators=(',', ':')) + '\n')
recipe = {'format': 'worker-fixture-recipe',
    'sources': [{'path': 'diagnostic-input.json',
                 'source': str(fixture.relative_to(repo)), 'sha256': digest(fixture)}],
    'generator': {'source': str(fixture.relative_to(repo)), 'sha256': digest(fixture)}}
recipe_path = root / 'diagnostic-recipe-person_3mps.json'
write(recipe_path, recipe)
contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
    'requirements': [{'disposition_index': 0,
        'requirement': plan['requirement_dispositions'][0]['requirement'],
        'source': str(assignment_path.relative_to(repo)),
        'output_key': 'alley_original_exposure', 'method': 'measure_alley',
        'value_type': 'object', 'kind': 'measured',
        'inputs': ['participant_footprints.jsonl', 'ego_motion.jsonl',
                   'trace.jsonl', 'video_frames.jsonl']}],
    'negative': {'remove': ['ego_motion.jsonl'],
                 'error_contains': 'Missing required source: ego_motion.jsonl'}}
contract_path = root / 'cases' / 'measurement-contract-person_3mps.json'
write(contract_path, contract)
construction_manifest = read(root / 'construction-probe-manifest.json')
selected = next(c for c in construction_manifest['cases'] if c['case_id'] == case_id)
runtime_manifest = repo / 'runtime' / 'SOURCE-MANIFEST.json'
manifest = {'format': 'worker-compatibility-manifest',
            'assignment_id': aid,
            'runtime_manifest_sha256': digest(runtime_manifest),
            'cases': [{**selected,
                'kind': 'delivery',
                'measurement_contract': str(contract_path.relative_to(root)),
                'measurement_procedure': {'entrypoint': 'alley_finalizer.py'},
                'fixture_recipe': str(recipe_path.relative_to(repo)),
                'acquisition': {
                    'participant_footprints': {
                        'entrypoint': 'alley_finalizer.py',
                        'method': 'original Native actor polygons preserved and projected to a saved structured channel',
                        'evidence': 'participant_footprints.jsonl joined to trace and frame map'},
                    'pedestrian_gap_m': {
                        'entrypoint': 'alley_finalizer.py',
                        'method': 'original Native subject/pedestrian polygon distance at saved frames',
                        'evidence': 'participant_footprints.jsonl joined to ego_motion.jsonl, trace and frame map'},
                    'property_gap_m': {
                        'entrypoint': 'alley_finalizer.py',
                        'method': 'original Native subject/property polygon distance at saved frames',
                        'evidence': 'participant_footprints.jsonl joined to ego_motion.jsonl, trace and frame map'},
                    'pedestrian_offset_m': {
                        'entrypoint': 'alley_finalizer.py',
                        'method': 'authored selected pedestrian lateral placement, distinct from original body gap',
                        'evidence': 'config.json fixed selected setup'}}}]}
write(root / 'probe-compatibility-manifest.json', manifest)
print('Bound first exact C10364 diagnostic fixture and source contract')
