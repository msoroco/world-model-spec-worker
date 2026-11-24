"""Derive a left-side approach CPU contrast from the proven right-side source."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = HERE.name + '__probe_02'
SOURCE = HERE / 'current-v2-contrast-sources'
BASE = HERE / 'current-v2-primary-sources'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value, sort_keys=True) + '\n' for value in values))


def shift(point):
    result = list(point)
    result[1] += 3.5
    return result


def main():
    primary = json.loads((HERE / 'current-v2-primary-construction.json').read_text())
    draft = json.loads((HERE / 'draft-cases/probe_02/primary/construction.json').read_text())
    primary_config = json.loads(next(item['content'] for item in primary['files'] if item['path'] == 'config.json'))
    contrast_config = json.loads(next(item['content'] for item in draft['files'] if item['path'] == 'config.json'))
    for key in ('candidate_id', 'required_atoms', 'source_packets', 'status'):
        contrast_config[key] = primary_config[key]
    contrast_config['case'] = {'case_id': CASE}
    contrast_config['supported_case_ids'] = [CASE]
    finalize = next(item['content'] for item in primary['files'] if item['path'] == 'finalize.py')
    finalize = finalize.replace('__probe_01', '__probe_02')
    finalize = finalize.replace("'requested': False", "'requested': True")
    finalize = finalize.replace("'matched': metric['first_left_active_frame'] is None",
                                "'matched': metric['first_left_active_frame'] is not None")
    assert "'requested': True" in finalize and "__probe_02" in finalize
    draft['files'] = [item for item in draft['files'] if item['path'] != 'config.json']
    draft['files'].extend([
        {'path': 'config.json', 'content': json.dumps(contrast_config, indent=2, sort_keys=True) + '\n'},
        {'path': 'finalize.py', 'content': finalize},
        {'path': 'zone_measure.py', 'content': (HERE / 'native/zone_measure.py').read_text()}])
    draft['recording_description'] = primary['recording_description']
    draft['status'] = 'unselected_cpu_diagnostic'
    construction = HERE / 'current-v2-contrast-construction.json'
    write(construction, draft)

    footprints = read_rows(BASE / 'vehicle-footprints.jsonl')
    trace = read_rows(BASE / 'trace.jsonl')
    evidence = read_rows(BASE / 'capture/evidence.jsonl')
    spec = json.loads((HERE / 'current-v2-primary-fixture-spec.json').read_text())
    for frame in range(240, 360):
        footprints[frame]['body_xy_m'] = [shift(p) for p in footprints[frame]['body_xy_m']]
        trace[frame]['position']['y'] += 3.5
        trace[frame]['position_m'][1] += 3.5
        evidence[frame]['ego']['position_m'][1] += 3.5
        evidence[frame]['ego']['body_vertices_m'] = [shift(p) for p in evidence[frame]['ego']['body_vertices_m']]
        evidence[frame]['world']['road_projection']['lane_id'] = 1
        graph = spec['graphs'][frame]
        graph['nodes'][0]['attributes']['vertex'][1] += 3.5
        graph['nodes'][0]['attributes']['threedbbox'] = [shift(p) for p in graph['nodes'][0]['attributes']['threedbbox']]
    rows(SOURCE / 'vehicle-footprints.jsonl', footprints)
    rows(SOURCE / 'trace.jsonl', trace)
    rows(SOURCE / 'capture/evidence.jsonl', evidence)
    (SOURCE / 'road-context.json').parent.mkdir(parents=True, exist_ok=True)
    (SOURCE / 'road-context.json').write_bytes((BASE / 'road-context.json').read_bytes())
    (SOURCE / 'video_frames.jsonl').write_bytes((BASE / 'video_frames.jsonl').read_bytes())
    capture_manifest = json.loads((BASE / 'capture/manifest.json').read_text())
    capture_manifest['sources']['trace.jsonl'] = sha(SOURCE / 'trace.jsonl')
    write(SOURCE / 'capture/manifest.json', capture_manifest)
    for graph in spec['graphs']:
        graph['attributes']['source'] = 'C111250 left-side approach contrast diagnostic'
    spec_path = HERE / 'current-v2-contrast-fixture-spec.json'
    write(spec_path, spec)
    sources = [{'path': str(path.relative_to(SOURCE)),
                'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
               for path in sorted(SOURCE.rglob('*')) if path.is_file()]
    recipe_path = HERE / 'current-v2-contrast-fixture-recipe.json'
    write(recipe_path, {'format': 'worker-fixture-recipe', 'sources': sources,
                        'generator': {'source': str(spec_path.relative_to(REPO)),
                                      'sha256': sha(spec_path)}})
    contract = json.loads((HERE / 'current-v2-primary-measurement-contract.json').read_text())
    contract['case_id'] = CASE
    contract_path = HERE / 'current-v2-contrast-measurement-contract.json'
    write(contract_path, contract)
    runtime = json.loads((REPO / 'batch.json').read_text())
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': HERE.name, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': runtime['runtime']['source_manifest_sha256'],
                'cases': [{'case_id': CASE, 'kind': 'draft_not_selected', 'id': 'primary',
                           'construction': construction.name,
                           'construction_sha256': sha(construction),
                           'fixture_recipe': str(recipe_path.relative_to(REPO)),
                           'measurement_contract': contract_path.name,
                           'measurement_procedure': {'entrypoint': 'finalize.py'},
                           'recording_description': draft['recording_description'],
                           'candidates': [],
                           'candidate_risk': {'status': 'physical',
                                              'reason': 'Original centerline and body pixels need review'}}]}
    manifest_path = HERE / 'current-v2-contrast-manifest.json'
    write(manifest_path, manifest)
    proposals_path = HERE / 'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    proposals['cases'] = [item for item in proposals['cases'] if item['case_id'] != CASE]
    proposals['cases'].append({'case_id': CASE, 'target_law_id': 'NRS-484B-213-2b',
                               'target_type': 'attempt',
                               'rationale': 'Unselected two-way intersection/left-side CPU contrast',
                               'variable_assignments': {'left_side_occupancy_requested': True},
                               'recording_description': draft['recording_description']})
    write(proposals_path, proposals)
    print(json.dumps({'manifest_sha256': sha(manifest_path), 'recipe_sha256': sha(recipe_path),
                      'construction_sha256': sha(construction)}))


if __name__ == '__main__':
    main()
