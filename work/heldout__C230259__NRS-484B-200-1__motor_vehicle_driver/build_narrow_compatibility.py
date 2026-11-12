"""Source-shaped narrow-road diagnostic with undecided legal sufficiency."""
import json
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__narrow_left'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    contract = json.loads((HERE / 'measurement-contract-baseline_left.json').read_text())
    contract['case_id'] = CASE
    write(HERE / 'measurement-contract-narrow_left.json', contract)
    proposal_path = HERE / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    row = json.loads(json.dumps(proposal['cases'][1]))
    row['case_id'] = CASE
    row['rationale'] = ('Original full-body left-half position on a measured narrow '
                        'two-way road candidate; legal width sufficiency separately reviewed.')
    row['variable_assignments'] = {
        'body_side': {'kind': 'controller', 'value': 'left'},
        'road_width_candidate_m': {'kind': 'world_setup', 'value': 6.},
        'legal_sufficiency': {'kind': 'world_setup', 'value': None},
    }
    row['recording_description'] = json.loads((HERE / 'construction-narrow_left.json').read_text())['recording_description']
    proposal['cases'] = [item for item in proposal['cases'] if item['case_id'] != CASE] + [row]
    write(proposal_path, proposal)
    diagnostic = json.loads((HERE / 'diagnostic-baseline_left.json').read_text())
    body = [json.loads(line) for line in diagnostic['files']['ego_road_frames.jsonl'].splitlines() if line]
    trace = [json.loads(line) for line in diagnostic['files']['trace.jsonl'].splitlines() if line]
    evidence = [json.loads(line) for line in diagnostic['files']['capture/evidence.jsonl'].splitlines() if line]
    if not body or len(body) != len(trace) or len(body) != len(evidence):
        raise ValueError('Narrow diagnostic original frame inventory differs')
    for frame, sample, packet in zip(body, trace, evidence):
        x, y = sample['position']['x'], 1.5
        frame['lane_id'] = 1
        frame['road_width_m'] = 6.
        frame['ego_corners_xy'] = [[x - 2.4, y - .9], [x + 2.4, y - .9],
                                   [x + 2.4, y + .9], [x - 2.4, y + .9]]
        frame['narrow_candidate_width_m'] = 6.
        frame['legal_sufficiency_decided'] = False
        sample['position']['y'] = y
        sample['position_m'][1] = y
        packet['ego']['position_m'][1] = y
        if 'body_vertices_m' in packet['ego']:
            old_y = packet['ego']['body_vertices_m'][0][1]
            for vertex in packet['ego']['body_vertices_m']:
                vertex[1] += y - old_y
    diagnostic['files']['ego_road_frames.jsonl'] = ''.join(json.dumps(row) + '\n' for row in body)
    diagnostic['files']['trace.jsonl'] = ''.join(json.dumps(row) + '\n' for row in trace)
    diagnostic['files']['capture/evidence.jsonl'] = ''.join(json.dumps(row) + '\n' for row in evidence)
    context = json.loads(diagnostic['files']['road_exception_context.json'])
    context['narrow_setup'] = {'candidate_max_road_width_m': 6.5,
                               'selected_road_widths_m': [6.] * len(body),
                               'subject_body_width_m': 1.8,
                               'legal_sufficiency': 'undecided',
                               'subject_path': 'left_half'}
    diagnostic['files']['road_exception_context.json'] = json.dumps(context) + '\n'
    capture_manifest = json.loads(diagnostic['files']['capture/manifest.json'])
    capture_manifest['case_id'] = CASE
    capture_manifest['sources']['trace.jsonl'] = sha256(diagnostic['files']['trace.jsonl'].encode()).hexdigest()
    diagnostic['files']['capture/manifest.json'] = json.dumps(capture_manifest, indent=2) + '\n'
    diagnostic['files']['narrow-diagnostic-provenance.json'] = json.dumps({
        'format': 'worker-diagnostic-source-note',
        'use': 'synthetic 6 m road width for CPU saved processing only',
        'legal_sufficiency_decided': False,
        'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False,
    }) + '\n'
    spec = HERE / 'diagnostic-narrow_left.json'
    spec.write_text(json.dumps(diagnostic, separators=(',', ':')) + '\n')
    ref = 'work/' + HERE.name + '/' + spec.name
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': ref, 'sha256': sha(spec)}],
              'generator': {'source': ref, 'sha256': sha(spec)}}
    write(HERE / 'fixture-recipe-narrow_left.json', recipe)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    entry['measurement_contract'] = 'measurement-contract-narrow_left.json'
    entry['fixture_recipe'] = 'work/' + HERE.name + '/fixture-recipe-narrow_left.json'
    write(manifest_path, manifest)
    return {'diagnostic_bytes': spec.stat().st_size, 'diagnostic_sha256': sha(spec)}


if __name__ == '__main__':
    print(json.dumps(build()))
