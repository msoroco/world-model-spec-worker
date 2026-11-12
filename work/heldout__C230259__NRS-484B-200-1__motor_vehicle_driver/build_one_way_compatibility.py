"""Source-shaped posted one-way diagnostic with undecided designation."""
import json
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__one_way_left'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    contract = json.loads((HERE / 'measurement-contract-baseline_left.json').read_text())
    contract['case_id'] = CASE
    write(HERE / 'measurement-contract-one_way_left.json', contract)
    proposal_path = HERE / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    row = json.loads(json.dumps(proposal['cases'][1]))
    row['case_id'] = CASE
    row['rationale'] = ('Original full-body left-half position on two same-direction lanes '
                        'with one-way sign actor; official designation and posting authority separately reviewed.')
    row['variable_assignments'] = {
        'body_side': {'kind': 'controller', 'value': 'left'},
        'same_direction_lane_count': {'kind': 'world_setup', 'value': 2},
        'posted_one_way_authority': {'kind': 'world_setup', 'value': None},
    }
    row['recording_description'] = json.loads((HERE / 'construction-one_way_left.json').read_text())['recording_description']
    proposal['cases'] = [item for item in proposal['cases'] if item['case_id'] != CASE] + [row]
    write(proposal_path, proposal)
    diagnostic = json.loads((HERE / 'diagnostic-baseline_left.json').read_text())
    body = [json.loads(line) for line in diagnostic['files']['ego_road_frames.jsonl'].splitlines() if line]
    if not body:
        raise ValueError('One-way diagnostic original body source missing')
    for frame in body:
        frame['lane_id'] = -2
        frame['lane_inventory'] = [
            {'lane_id': -1, 'width_m': 3.5, 'travel_tangent_xy': [1., 0.]},
            {'lane_id': -2, 'width_m': 3.5, 'travel_tangent_xy': [1., 0.]},
        ]
        frame['designation_verified'] = False
        frame['posting_authority_verified'] = False
    diagnostic['files']['ego_road_frames.jsonl'] = ''.join(json.dumps(row) + '\n' for row in body)
    first_x = body[0]['road_center_xy'][0]
    signs = [{'frame': frame['frame'], 'time_s': frame['time_s'],
              'actor_id': '34', 'blueprint_id': 'static.prop.oneway_sign',
              'position_m': [first_x + 5., -4.5, .1],
              'designation_verified': False, 'posting_authority_verified': False}
             for frame in body]
    diagnostic['files']['one_way_sign.jsonl'] = ''.join(json.dumps(row) + '\n' for row in signs)
    context = json.loads(diagnostic['files']['road_exception_context.json'])
    context['one_way_setup'] = {'lane_ids': [-1, -2], 'sign_actor_id': 34,
                                'official_designation': 'undecided',
                                'posting_authority': 'undecided',
                                'subject_path': 'left_half'}
    diagnostic['files']['road_exception_context.json'] = json.dumps(context) + '\n'
    capture_manifest = json.loads(diagnostic['files']['capture/manifest.json'])
    capture_manifest['case_id'] = CASE
    diagnostic['files']['capture/manifest.json'] = json.dumps(capture_manifest, indent=2) + '\n'
    diagnostic['files']['one-way-diagnostic-provenance.json'] = json.dumps({
        'format': 'worker-diagnostic-source-note',
        'use': 'synthetic same-direction lanes and sign actor for CPU processing only',
        'official_designation_verified': False,
        'posting_authority_verified': False,
        'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False,
    }) + '\n'
    spec = HERE / 'diagnostic-one_way_left.json'
    spec.write_text(json.dumps(diagnostic, separators=(',', ':')) + '\n')
    ref = 'work/' + HERE.name + '/' + spec.name
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': ref, 'sha256': sha(spec)}],
              'generator': {'source': ref, 'sha256': sha(spec)}}
    write(HERE / 'fixture-recipe-one_way_left.json', recipe)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    entry['measurement_contract'] = 'measurement-contract-one_way_left.json'
    entry['fixture_recipe'] = 'work/' + HERE.name + '/fixture-recipe-one_way_left.json'
    write(manifest_path, manifest)
    return {'diagnostic_bytes': spec.stat().st_size, 'diagnostic_sha256': sha(spec)}


if __name__ == '__main__':
    print(json.dumps(build()))
