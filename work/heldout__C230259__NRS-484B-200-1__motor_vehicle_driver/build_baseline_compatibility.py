"""Bind the first right-half baseline to source-shaped CPU compatibility inputs."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASE = ASSIGNMENT + '__baseline_right'
INPUT = f'inputs/{ASSIGNMENT}/assignment.json'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def build():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if 'requirement_dispositions' not in plan:
        plan['requirement_dispositions'] = [{
            'requirement': 'Original full-body right-half position and separately sourced NRS 484B.200(1) exception premises',
            'source': INPUT, 'status': 'selected_required',
            'case_ids': [row['case_id'] for row in plan['cases']],
            'evidence_or_gap': 'No accepted recordings; original geometry and exception context required for all seven planned exact cases.'}]
        write(plan_path, plan)
    finalizer_path = HERE / 'right_half_finalizer.py'
    construction_path = HERE / 'construction.json'
    construction = json.loads(construction_path.read_text())
    for item in construction['files']:
        if item['path'] in ('right_half_finalizer.py', 'runner.py'):
            item['content'] = (HERE / item['path']).read_text()
    write(construction_path, construction)
    contract = {'format': 'worker-measurement-contract', 'case_id': CASE,
                'requirements': [{
                    'disposition_index': 0,
                    'requirement': plan['requirement_dispositions'][0]['requirement'],
                    'source': INPUT, 'output_key': 'right_half_observation',
                    'method': 'analyze', 'value_type': 'object', 'kind': 'measured',
                    'inputs': ['ego_road_frames.jsonl', 'road_exception_context.json',
                               'video_frames.jsonl', 'trace.jsonl']}],
                'negative': {'remove': ['ego_road_frames.jsonl'],
                             'error_contains': 'Missing required source: ego_road_frames.jsonl'}}
    write(HERE / 'measurement-contract-baseline_right.json', contract)
    proposal_dir = HERE / 'proposals'
    proposal_dir.mkdir(exist_ok=True)
    proposal = {'case_id': CASE, 'target_law_id': 'NRS-484B-200-1',
                'target_type': 'boundary_probe',
                'rationale': 'Whole-body right-half baseline on a source-observed two-way road; width sufficiency and exceptions remain reviewed judgments.',
                'variable_assignments': {
                    'body_side': {'kind': 'controller', 'value': 'right'},
                    'two_way_road': {'kind': 'world_setup', 'value': True}},
                'unresolved_judgment_calls': ['sufficient width', 'exception applicability'],
                'recording_description': construction['recording_description']}
    write(proposal_dir / 'cases.json', {'cases': [proposal]})
    other = sorted(ROOT.glob('work/heldout__C230627*/diagnostic-prohibition_403_2.json'))
    if len(other) != 1:
        raise ValueError('Source-shaped local diagnostic template missing')
    diagnostic = json.loads(other[0].read_text())
    trace = [json.loads(line) for line in diagnostic['files']['trace.jsonl'].splitlines() if line]
    frames = []
    for row in trace:
        x = float(row['position']['x'])
        frames.append({'frame': row['frame'], 'time_s': row['time_s'],
                       'road_id': 1, 'lane_id': -1, 'road_center_xy': [x, 0.0],
                       'road_travel_tangent_xy': [1.0, 0.0], 'road_width_m': 7.0,
                       'ego_corners_xy': [[x-2.4, -2.9], [x+2.4, -2.9],
                                          [x+2.4, -1.1], [x-2.4, -1.1]]})
    diagnostic['files']['ego_road_frames.jsonl'] = ''.join(json.dumps(row) + '\n' for row in frames)
    context = {
        key: {'value': None, 'source_ref': None} for key in
        ('passing_same_direction', 'right_half_closed', 'three_lane_highway',
         'posted_one_way', 'insufficient_width')}
    context['road_exception_context'] = {'source': 'synthetic source-shaped diagnostic',
                                         'review_status': 'undecided'}
    diagnostic['files']['road_exception_context.json'] = json.dumps(context) + '\n'
    diagnostic['files']['right_half_fixture_provenance.json'] = json.dumps({
        'kind': 'diagnostic_text', 'source': 'C230627 source-shaped CPU graph/media fixture',
        'meaning': 'Synthetic right-half road/body join only; no physical or legal acceptance'}) + '\n'
    for key in list(diagnostic['files']):
        if key.startswith('u_turn_'):
            del diagnostic['files'][key]
    (HERE / 'diagnostic-baseline_right.json').write_text(json.dumps(diagnostic, separators=(',', ':'), ensure_ascii=False) + '\n')
    diagnostic_ref = f'work/{ASSIGNMENT}/diagnostic-baseline_right.json'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': diagnostic_ref,
                           'sha256': digest(HERE / 'diagnostic-baseline_right.json')}],
              'generator': {'source': diagnostic_ref,
                            'sha256': digest(HERE / 'diagnostic-baseline_right.json')}}
    # Generator spec is inventoried directly; it is not copied into acquisition.
    recipe['sources'] = [recipe['sources'][0]]
    write(HERE / 'fixture-recipe-baseline_right.json', recipe)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = manifest['cases'][0]
    entry['construction_sha256'] = digest(construction_path)
    entry['measurement_contract'] = 'measurement-contract-baseline_right.json'
    entry['fixture_recipe'] = f'work/{ASSIGNMENT}/fixture-recipe-baseline_right.json'
    write(manifest_path, manifest)
    return {'construction_sha256': digest(construction_path),
            'manifest_sha256': digest(manifest_path),
            'diagnostic_bytes': (HERE / 'diagnostic-baseline_right.json').stat().st_size}


if __name__ == '__main__':
    print(json.dumps(build()))
