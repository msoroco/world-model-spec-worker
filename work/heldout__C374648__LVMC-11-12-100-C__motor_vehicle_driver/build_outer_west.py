"""Add the controlled westbound outer-origin left turn to the first exact pair."""

from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CASE = ASSIGNMENT + '__left_outer_west'


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, value, *, compact=False):
    Path(path).write_text(json.dumps(value, separators=(',', ':') if compact else None,
                                     indent=None if compact else 2, ensure_ascii=False)+'\n')


def build():
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'] = [row for row in manifest['cases'] if row['case_id'] != CASE]
    config = json.loads((HERE/'config.json').read_text())
    config['selected_case_id'] = CASE
    config['case']['case_id'] = CASE
    write(HERE/'config-outer_west.json', config)
    paths = ['config.json', 'west_outer_runner.py', 'center_turn_cameras.py',
             'center_turn_construction.py', 'turn_origin_capture.py',
             'turn_origin_measurement.py', 'turn_origin_finalizer.py',
             'west_outer_finalizer.py',
             'tests/test_west_outer_source.py', 'tests/test_west_source.py',
             'tests/test_turn_origin_finalizer.py',
             'tests/test_turn_origin_measurement.py',
             'tests/test_center_turn_construction.py']
    construction = json.loads((HERE/'construction.json').read_text())
    construction['case_id'] = CASE
    construction['entrypoint'] = 'west_outer_runner.py'
    construction['files'] = [{'path': path,
                              'content': (HERE/('config-outer_west.json' if path == 'config.json' else path)).read_text()}
                             for path in paths]
    construction['measurement_plan']['saved_only_finalizer'] = 'west_outer_finalizer.py'
    construction['mechanisms']['route'] = 'same connected marked Native westbound center/outer selector; outer origin'
    construction['mechanisms']['control'] = 'bounded westbound outer-lane left route feedback to same exit'
    construction['mechanisms']['construction_status'] = 'outer_exact_primary_cpu_proof_pending'
    write(HERE/'construction-outer_west.json', construction)
    plan = json.loads((HERE/'case-plan.json').read_text())
    disposition = plan['requirement_dispositions'][1]
    contract = {'format': 'worker-measurement-contract', 'case_id': CASE,
                'requirements': [{'disposition_index': 1,
                                  'requirement': disposition['requirement'],
                                  'source': disposition['source'],
                                  'output_key': 'turn_origin_observation',
                                  'method': 'analyze', 'value_type': 'object',
                                  'kind': 'measured',
                                  'inputs': ['turn_origin_native.jsonl',
                                             'case_context.json', 'video_frames.jsonl',
                                             'trace.jsonl']}],
                'negative': {'remove': ['turn_origin_native.jsonl'],
                             'error_contains': 'Missing required source: turn_origin_native.jsonl'}}
    write(HERE/'measurement-contract-left_outer_west.json', contract)
    diagnostic = json.loads((HERE/'diagnostic-left_center_west.json').read_text())
    rows = [json.loads(line) for line in diagnostic['files']['turn_origin_native.jsonl'].splitlines()]
    for row in rows:
        row['lane_id'] = -2
    diagnostic['files']['turn_origin_native.jsonl'] = ''.join(json.dumps(row)+'\n' for row in rows)
    context = json.loads(diagnostic['files']['case_context.json'])
    context['case_id'] = CASE
    context['case_context']['case_id'] = CASE
    diagnostic['files']['case_context.json'] = json.dumps(context)+'\n'
    diagnostic['files']['center_turn_fixture_provenance.json'] = json.dumps({
        'kind': 'diagnostic_text', 'source': 'diagnostic-left_center_west.json',
        'meaning': 'Synthetic westbound outer-origin lane difference only; no Native physical or legal claim'})+'\n'
    diagnostic_path = HERE/'diagnostic-left_outer_west.json'
    write(diagnostic_path, diagnostic, compact=True)
    ref = f'work/{ASSIGNMENT}/{diagnostic_path.name}'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': ref,
                           'sha256': sha(diagnostic_path)}],
              'generator': {'source': ref, 'sha256': sha(diagnostic_path)}}
    write(HERE/'fixture-recipe-left_outer_west.json', recipe)
    proposal_path = HERE/'proposals/cases.json'
    proposals = json.loads(proposal_path.read_text())
    proposals['cases'] = [row for row in proposals['cases'] if row['case_id'] != CASE]
    proposal = dict(proposals['cases'][0])
    proposal['case_id'] = CASE
    proposal['rationale'] = 'Original outer-lane origin followed by a left turn to the same exit as the center-lane comparison; designation authority unresolved.'
    proposal['variable_assignments'] = {
        'origin_lane': {'kind': 'controller', 'value': 'outer adjacent'},
        'approach_direction': {'kind': 'world_setup', 'value': 'west'}}
    proposals['cases'].append(proposal)
    write(proposal_path, proposals)
    manifest['cases'].append({
        'case_id': CASE, 'kind': 'delivery',
        'construction': 'construction-outer_west.json',
        'construction_sha256': sha(HERE/'construction-outer_west.json'),
        'measurement_procedure': {'entrypoint': 'west_outer_finalizer.py'},
        'measurement_contract': 'measurement-contract-left_outer_west.json',
        'fixture_recipe': f'work/{ASSIGNMENT}/fixture-recipe-left_outer_west.json',
        'candidate_risk': {'status': 'physical',
                           'reason': 'Westbound outer lane may cross into candidate center lane before turn; map and motion require Native review'},
        'candidates': []})
    write(manifest_path, manifest)
    return {'manifest_sha256': sha(manifest_path),
            'diagnostic_bytes': diagnostic_path.stat().st_size}


if __name__ == '__main__':
    print(json.dumps(build()))
