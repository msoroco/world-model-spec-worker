"""Build source-shaped closure-left diagnostics without deciding authority."""
import json
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__closure_left'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    contract = json.loads((HERE / 'measurement-contract-baseline_left.json').read_text())
    contract['case_id'] = CASE
    write(HERE / 'measurement-contract-closure_left.json', contract)
    proposal_path = HERE / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    row = json.loads(json.dumps(proposal['cases'][1]))
    row['case_id'] = CASE
    row['rationale'] = ('Original full-body left-half position beside right-half closure devices; '
                        'traffic-control authority requires separate review.')
    row['variable_assignments'] = {
        'body_side': {'kind': 'controller', 'value': 'left'},
        'closure_device_count': {'kind': 'world_setup', 'value': 3},
        'authorized_right_half_closure': {'kind': 'world_setup', 'value': None},
    }
    row['recording_description'] = json.loads((HERE / 'construction-closure_left.json').read_text())['recording_description']
    proposal['cases'] = [item for item in proposal['cases'] if item['case_id'] != CASE] + [row]
    write(proposal_path, proposal)
    diagnostic = json.loads((HERE / 'diagnostic-baseline_left.json').read_text())
    road = [json.loads(line) for line in diagnostic['files']['ego_road_frames.jsonl'].splitlines() if line]
    if not road:
        raise ValueError('Closure diagnostic has no original body/road frames')
    devices = []
    first_x, first_y = road[0]['road_center_xy']
    cone_x, cone_y = first_x + 12., first_y - road[0]['road_width_m'] / 4.
    for frame in road:
        devices.append({'frame': frame['frame'], 'time_s': frame['time_s'],
                        'devices': [
                            {'actor_id': str(i + 1), 'blueprint_id': 'static.prop.trafficcone01',
                             'position_m': [cone_x, cone_y + offset, 0.05]}
                            for i, offset in enumerate((-1.1, 0., 1.1))],
                        'authority_verified': False})
    diagnostic['files']['closure_devices.jsonl'] = ''.join(json.dumps(row) + '\n' for row in devices)
    context = json.loads(diagnostic['files']['road_exception_context.json'])
    context['right_half_closed'] = {'value': None, 'source_ref': None}
    context['closure_setup'] = {'device_actor_ids': [1, 2, 3],
                                'right_half_closure_authority': 'undecided',
                                'original_device_source': 'closure_devices.jsonl',
                                'subject_path': 'left_half'}
    diagnostic['files']['road_exception_context.json'] = json.dumps(context) + '\n'
    capture_manifest = json.loads(diagnostic['files']['capture/manifest.json'])
    capture_manifest['case_id'] = CASE
    diagnostic['files']['capture/manifest.json'] = json.dumps(capture_manifest, indent=2) + '\n'
    spec = HERE / 'diagnostic-closure_left.json'
    spec.write_text(json.dumps(diagnostic, separators=(',', ':')) + '\n')
    ref = 'work/' + HERE.name + '/' + spec.name
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': ref, 'sha256': sha(spec)}],
              'generator': {'source': ref, 'sha256': sha(spec)}}
    write(HERE / 'fixture-recipe-closure_left.json', recipe)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    entry['measurement_contract'] = 'measurement-contract-closure_left.json'
    entry['fixture_recipe'] = 'work/' + HERE.name + '/fixture-recipe-closure_left.json'
    write(manifest_path, manifest)
    return {'diagnostic_bytes': spec.stat().st_size, 'diagnostic_sha256': sha(spec)}


if __name__ == '__main__':
    print(json.dumps(build()))
