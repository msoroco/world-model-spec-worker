"""Validate the two fixed road-exit attempts without assigning legal labels."""
import hashlib
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assignment = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
    template = json.loads((HERE / 'proposals/template.json').read_text())
    for index, judgment in enumerate(template['structure']['judgment_calls_needed']):
        observable = json.loads((HERE / 'proposals' / f'judgment_observables_{index}.json').read_text())
        judgment['observable_requirements'] = observable['observable_requirements']
    binding = json.loads((HERE / 'proposals/bindings.json').read_text())
    law_id, actor, cell_id = (assignment[key] for key in ('law_id', 'actor', 'cell_id'))
    names = [v['name'] for v in binding['variable_parameters']]
    values = {
        'driveway_sidewalk_geometry': ('world_setup', 'connected road-to-private-driveway path crossing a source-verified sidewalk area', 'structured'),
        'district_context': ('world_setup', 'source-supported residence district', 'structured'),
        'pedestrian_route': ('world_setup', 'separate pedestrian on sidewalk with fixed route', 'structured'),
        'roadway_traffic_context': ('world_setup', 'fixed roadway traffic observation; roadway-entry duty not exercised', 'structured'),
        'ego_trajectory': ('subject_behavior', None, 'structured'),
        'ego_speed': ('subject_behavior', None, 'm/s'),
        'commanded_approach_speed': ('controller', 2.0, 'm/s'),
        'commanded_stop_policy': ('controller', 'stop_before_sidewalk', 'category'),
        'commanded_turn_path': ('controller', 'road-to-driveway', 'structured')}
    assert set(values) == set(names)
    assignments = {name: {'kind': kind, 'value': value, 'unit': unit}
                   for name, (kind, value, unit) in values.items()}
    def channel(name, unit, method):
        return {'name': name, 'unit': unit, 'sampling_rate_hz': 20,
                'method': method, 'time_window': 'entire 30 s or longer original Native capture',
                'reference_frame': 'source-verified map and original frame times',
                'uncertainty': '50 ms sampling interval; physical setup and pixel visibility unverified'}
    recording = {
        'channels': [
            channel('ego_pose_speed_footprint', 'structured', 'original frame-joined ego pose, speed, bounding box and sidewalk overlap'),
            channel('pedestrian_vehicle_trace', 'structured', 'original frame-joined ego and pedestrian poses, speeds and footprints'),
            channel('roadway_vehicle_trace', 'structured', 'original frame-joined ego and approaching roadway vehicle poses and footprints')],
        'context_inputs': [
            {'name': 'sidewalk_geometry', 'unit': 'structured', 'method': 'source-verified sidewalk polygon and driveway edge'},
            {'name': 'pedestrian_sidewalk_route', 'unit': 'structured', 'method': 'source-verified pedestrian sidewalk waypoints'},
            {'name': 'roadway_entry_geometry', 'unit': 'structured', 'method': 'source-verified roadway boundary and approach lanes'}],
        'limitations': [
            'This cell exits the road into a driveway; it does not physically exercise upon-entering-roadway yield.',
            'Attempted stop policy and synthetic values are not observed Native results or legal conclusions.']}
    prefix = HERE.name + '__'
    baseline = {
        'case_id': prefix + 'baseline', 'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Neutral route definition for the road-to-driveway sidewalk crossing.',
        'variable_assignments': deepcopy(assignments), 'recording_description': recording,
        'unresolved_judgment_calls': []}
    cases = [baseline]
    for suffix, policy in [('stop_before_sidewalk', 'stop_before_sidewalk'),
                           ('cross_without_stop', 'cross_without_stop')]:
        variant = deepcopy(assignments)
        variant['commanded_stop_policy']['value'] = policy
        cases.append({
            'case_id': prefix + suffix, 'target_law_id': law_id,
            'target_type': 'boundary_probe',
            'rationale': 'Controlled physical stop-policy attempt; no legal judgment is assigned.',
            'variable_assignments': variant, 'recording_description': recording,
            'unresolved_judgment_calls': [j['phrase'] for j in template['structure']['judgment_calls_needed']],
            'paired_probe_id': prefix + 'sidewalk_stop_pair',
            'deliberate_differences': ['commanded_stop_policy'],
            'probe': {'primary_variable': 'commanded_stop_policy',
                      'comparison_or_standard': 'same sidewalk geometry, pedestrian route and capture profile',
                      'target_value_or_branch': policy}})
    missing = [
        'Native-verified sidewalk boundary and feasible stop positions have not been constructed; no fixed physical range can be justified.',
        'Pedestrian route and safe arrival-offset range have not been physically constructed or source-verified.',
        'Current exit_road catalog maneuver does not exercise roadway entry; select a compatible roadway-entry cell for this branch.']
    sweeps = []
    for index, judgment in enumerate(template['structure']['judgment_calls_needed']):
        sweeps.append({'sweep_id': f'c213851_judgment_{index}', 'target_law_id': law_id,
                       'judgment_refs': [judgment], 'status': 'incomplete',
                       'rationale': 'Freeze the source question and exact missing physical inputs before choosing a range.',
                       'missing_inputs': [missing[index]]})
    result = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
              'cases': cases, 'sweep_specs': sweeps}
    stages.validate('cases', result, {
        'request': {'cell': assignment['cell'], 'actor': actor},
        'dependencies': [binding], 'templates': [template]})
    path = HERE / 'proposals/cases.json'
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    index_path = HERE / 'proposals/semantic-index.json'
    index = json.loads(index_path.read_text())
    index['stages']['cases'] = {'path': 'proposals/cases.json', 'sha256': sha(path)}
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + '\n')
    proof_path = HERE / 'proposals/semantic-foundation-proof.json'
    proof = json.loads(proof_path.read_text())
    proof['references']['cases'] = {'path': 'proposals/cases.json', 'sha256': sha(path)}
    proof['cases_stage_validated'] = True
    if 'cases' not in proof['stages_validated']:
        proof['stages_validated'].append('cases')
    proof_path.write_text(json.dumps(proof, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(cases), 'incomplete_sweeps': len(sweeps),
                      'proof_sha256': sha(proof_path)}))


if __name__ == '__main__':
    if '/.runtime-work/' not in os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', ''):
        raise SystemExit('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work/')
    main()
