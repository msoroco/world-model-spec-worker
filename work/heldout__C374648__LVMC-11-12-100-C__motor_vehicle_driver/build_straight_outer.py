"""Build the exact eastbound outer-lane straight-travel CPU construction."""

from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CASE = ASSIGNMENT+'__straight_outer_east'


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, value, *, compact=False):
    Path(path).write_text(json.dumps(value, separators=(',', ':') if compact else None,
                                     indent=None if compact else 2,
                                     ensure_ascii=False)+'\n')


def build():
    config = json.loads((HERE/'config.json').read_text())
    config['selected_case_id'] = CASE
    config['case']['case_id'] = CASE
    config['case']['recording_description']['channels'][0]['name'] = 'straight_use_observation'
    config['case']['recording_description']['channels'][0]['method'] = 'joined original Native lane and straight heading rows'
    write(HERE/'config-straight_outer_east.json', config)
    paths = ['config.json', 'straight_outer_runner.py', 'straight_construction.py',
             'center_turn_cameras.py', 'center_turn_construction.py',
             'turn_origin_capture.py', 'straight_use_measurement.py',
             'turn_origin_measurement.py', 'turn_origin_finalizer.py',
             'straight_outer_finalizer.py',
             'tests/test_straight_outer_source.py',
             'tests/test_straight_use_measurement.py',
             'tests/test_straight_construction.py',
             'tests/test_turn_origin_finalizer.py',
             'tests/test_center_turn_construction.py']
    construction = json.loads((HERE/'construction.json').read_text())
    construction['case_id'] = CASE
    construction['entrypoint'] = 'straight_outer_runner.py'
    construction['files'] = [
        {'path': path, 'content':
         (HERE/('config-straight_outer_east.json' if path == 'config.json' else path)).read_text()}
        for path in paths]
    construction['recording_description'] = config['case']['recording_description']
    construction['measurement_plan']['derived_channels'] = ['straight_use_observation']
    construction['measurement_plan']['saved_only_finalizer'] = 'straight_outer_finalizer.py'
    construction['mechanisms']['route'] = 'connected marked Native outer approach and heading-consistent straight exit'
    construction['mechanisms']['control'] = 'bounded straight route feedback from adjacent outer lane'
    construction['mechanisms']['construction_status'] = 'straight_outer_exact_primary_cpu_proof_pending'
    construction['static_checks'][1] = 'Marked connected center/outer approach and straight exit'
    write(HERE/'construction-straight_outer_east.json', construction)
    plan = json.loads((HERE/'case-plan.json').read_text())
    disposition = plan['requirement_dispositions'][0]
    contract = {'format': 'worker-measurement-contract', 'case_id': CASE,
                'requirements': [{'disposition_index': 0,
                                  'requirement': disposition['requirement'],
                                  'source': disposition['source'],
                                  'output_key': 'straight_use_observation',
                                  'method': 'analyze', 'value_type': 'object',
                                  'kind': 'measured',
                                  'inputs': ['turn_origin_native.jsonl',
                                             'case_context.json', 'video_frames.jsonl',
                                             'trace.jsonl']}],
                'negative': {'remove': ['turn_origin_native.jsonl'],
                             'error_contains': 'Missing required source: turn_origin_native.jsonl'}}
    write(HERE/'measurement-contract-straight_outer_east.json', contract)
    diagnostic = json.loads((HERE/'diagnostic-left_center_east.json').read_text())
    rows = [json.loads(line) for line in diagnostic['files']['turn_origin_native.jsonl'].splitlines()]
    for row in rows:
        row['ego_forward_xy'] = [1, 0]
        row['lane_id'] = 2
    diagnostic['files']['turn_origin_native.jsonl'] = ''.join(json.dumps(row)+'\n' for row in rows)
    context = json.loads(diagnostic['files']['case_context.json'])
    context['case_id'] = CASE
    context['target_exit_lane_id'] = 2
    context['target_exit_road_id'] = 26
    context['case_context']['case_id'] = CASE
    context['case_context']['target_exit_lane_id'] = 2
    context['case_context']['target_exit_road_id'] = 26
    context['requested_maneuver'] = 'straight'
    context['case_context']['requested_maneuver'] = 'straight'
    diagnostic['files']['case_context.json'] = json.dumps(context)+'\n'
    diagnostic['files']['center_turn_fixture_provenance.json'] = json.dumps({
        'kind': 'diagnostic_text', 'source': 'diagnostic-left_center_east.json',
        'meaning': 'Synthetic straight-heading diagnostic only; no Native physical or legal claim'})+'\n'
    diagnostic_path = HERE/'diagnostic-straight_outer_east.json'
    write(diagnostic_path, diagnostic, compact=True)
    ref = f'work/{ASSIGNMENT}/{diagnostic_path.name}'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': ref,
                           'sha256': sha(diagnostic_path)}],
              'generator': {'source': ref, 'sha256': sha(diagnostic_path)}}
    write(HERE/'fixture-recipe-straight_outer_east.json', recipe)
    proposal_path = HERE/'proposals/cases.json'
    proposals = json.loads(proposal_path.read_text())
    proposals['cases'] = [row for row in proposals['cases'] if row['case_id'] != CASE]
    proposal = dict(proposals['cases'][0])
    proposal['case_id'] = CASE
    proposal['rationale'] = 'Original candidate outer-lane occupancy with observed straight heading; designation and statutory necessity unresolved.'
    proposal['variable_assignments'] = {
        'origin_lane': {'kind': 'controller', 'value': 'outer adjacent'},
        'maneuver': {'kind': 'controller', 'value': 'straight'},
        'approach_direction': {'kind': 'world_setup', 'value': 'east'}}
    proposals['cases'].append(proposal)
    write(proposal_path, proposals)
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'] = [row for row in manifest['cases'] if row['case_id'] != CASE]
    manifest['cases'].append({
        'case_id': CASE, 'kind': 'delivery',
        'construction': 'construction-straight_outer_east.json',
        'construction_sha256': sha(HERE/'construction-straight_outer_east.json'),
        'measurement_procedure': {'entrypoint': 'straight_outer_finalizer.py'},
        'measurement_contract': 'measurement-contract-straight_outer_east.json',
        'fixture_recipe': f'work/{ASSIGNMENT}/fixture-recipe-straight_outer_east.json',
        'candidate_risk': {'status': 'physical',
                           'reason': 'Connected straight exit or sustained outer-lane occupancy may be absent; map designation and motion require Native review'},
        'candidates': []})
    write(manifest_path, manifest)
    return {'manifest_sha256': sha(manifest_path),
            'diagnostic_bytes': diagnostic_path.stat().st_size}


if __name__ == '__main__':
    print(json.dumps(build()))
