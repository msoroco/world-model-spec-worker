"""Construct the left-approach comparison using a reflected diagnostic source.

This is a synthetic CPU fixture. The selected Native site remains unverified.
"""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUT = ROOT / 'cases/source_verified_other_left_near_time'
RIGHT = ROOT.name + '__source_verified_other_right_near_time'
LEFT = ROOT.name + '__source_verified_other_left_near_time'


def dump(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def mirror_body(vertices):
    return [[vertex[0], -vertex[1], *vertex[2:]] for vertex in vertices]


def mirror_actor(actor):
    actor['position_m'][1] *= -1
    actor['heading_deg'] = -90
    actor['velocity_mps'][1] *= -1
    actor['body_vertices_m'] = mirror_body(actor['body_vertices_m'])


def mirror_observation(observation):
    other = next(p for p in observation['participants'] if p['actor_id'] == 102)
    mirror_actor(other)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    construction = copy.deepcopy(json.loads((ROOT / 'construction.json').read_text()))
    construction['case_id'] = LEFT
    construction['status'] = 'synthetic_diagnostic_only'
    by_name = {item['path']: item for item in construction['files']}
    config = json.loads(by_name['config.json']['content'])
    config['selected_case_id'] = LEFT
    config['supported_case_ids'] = [RIGHT, LEFT]
    site = config['site']
    site['other_approach'] = [0, 10, 0, -90]
    site['other_entry'] = [0, 4, 0, -90]
    site['routes']['other'] = [[0, 10], [0, 4], [0, 0], [0, -10]]
    packet = json.loads(by_name['site-review.json']['content'])
    packet['site'] = site
    packet_text = dump(packet)
    by_name['site-review.json']['content'] = packet_text
    config['site_review']['sha256'] = sha(packet_text)
    by_name['config.json']['content'] = dump(config)
    runner = by_name['runner.py']['content'].replace(RIGHT, LEFT)
    runner = runner.replace('Exact right-hand median-entry case required',
                            'Exact left-hand median-entry case required')
    by_name['runner.py']['content'] = runner
    pair = by_name['native_pair.py']['content']
    old = 'if lateral <= 0 or reciprocal >= 0:\n        raise ValueError("Other Native approach is not on ego right")'
    new = 'if lateral >= 0 or reciprocal <= 0:\n        raise ValueError("Other Native approach is not on ego left")'
    if old not in pair:
        raise ValueError('Native pair source changed; review left-side condition')
    by_name['native_pair.py']['content'] = pair.replace(old, new)
    by_name['tests/test_bundle.py']['content'] = by_name['tests/test_bundle.py']['content'].replace(
        "self.assertEqual(validate_config(config)['selected_case_id'],config['selected_case_id'])",
        "self.assertEqual(validate_config(config)['selected_case_id'],config['selected_case_id'])\n"
        "  self.assertEqual(config['selected_case_id'].rsplit('__',1)[-1],"
        "'source_verified_other_left_near_time')")
    construction['recording_description'] = config['recording_description']
    ctext = dump(construction)
    (OUT / 'construction.json').write_text(ctext)

    diagnostic = copy.deepcopy(json.loads((ROOT / 'diagnostic.json').read_text()))
    files = diagnostic['files']
    history = [json.loads(line) for line in files['crossing_history.jsonl'].splitlines()]
    for row in history:
        other = row['other']
        other['position_xy_m'][1] *= -1
        other['body_vertices_xy_m'] = mirror_body(other['body_vertices_xy_m'])
    files['crossing_history.jsonl'] = ''.join(json.dumps(row, allow_nan=False) + '\n' for row in history)
    geometry = json.loads(files['road_geometry.json'])
    geometry['other_approach_heading_deg'] = -90
    geometry['other_approach_origin_xy_m'] = [0, 8]
    files['road_geometry.json'] = dump(geometry)
    evidence = [json.loads(line) for line in files['capture/evidence.jsonl'].splitlines()]
    for row in evidence:
        mirror_observation(row['original_observations'])
    files['capture/evidence.jsonl'] = ''.join(json.dumps(row, allow_nan=False) + '\n' for row in evidence)
    for graph in diagnostic['graphs']:
        mirror_observation(graph['attributes']['observed_evidence'])
    xodr = files['road.xodr']
    old = 'synthetic other highway" length="30" id="2" junction="7"><link/><planView><geometry s="0" x="0" y="-15" hdg="1.5707963267948966"'
    new = 'synthetic other highway" length="30" id="2" junction="7"><link/><planView><geometry s="0" x="0" y="15" hdg="-1.5707963267948966"'
    if old not in xodr:
        raise ValueError('Synthetic OpenDRIVE other road changed')
    files['road.xodr'] = xodr.replace(old, new)
    capture_manifest = json.loads(files['capture/manifest.json'])
    capture_manifest['case_id'] = LEFT
    capture_manifest['sources']['road.xodr'] = sha(files['road.xodr'])
    files['capture/manifest.json'] = dump(capture_manifest)
    diagnostic_path = OUT / 'diagnostic.json'
    diagnostic_path.write_text(dump(diagnostic))
    origin = OUT / 'fixture-origin.json'
    origin.write_text(dump({'format': 'worker-synthetic-diagnostic-origin',
                            'case_id': LEFT, 'physical_evidence': False,
                            'purpose': 'CPU compatibility only'}))
    def ref(path):
        return {'source': str(path.relative_to(REPO)),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'fixture-origin.json', **ref(origin)}],
              'generator': ref(diagnostic_path)}
    (OUT / 'diagnostic-recipe.json').write_text(dump(recipe))
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if LEFT not in {entry['case_id'] for entry in manifest['cases']}:
        primary = copy.deepcopy(manifest['cases'][0])
        primary.update({'case_id': LEFT, 'construction': str((OUT / 'construction.json').relative_to(ROOT)),
                        'construction_sha256': sha(ctext),
                        'fixture_recipe': str((OUT / 'diagnostic-recipe.json').relative_to(REPO)),
                        'measurement_contract': 'measurement-contract.json',
                        'candidate_risk': {'status': 'physical',
                            'reason': 'Left approach lane, entry order or camera coverage may fail Native review'},
                        'candidates': []})
        for key in ('offline', 'compatibility', 'negative'):
            primary.pop(key, None)
        manifest['cases'].append(primary)
        manifest_path.write_text(dump(manifest))
    proposals = ROOT / 'proposals/cases.json'
    proposal = json.loads(proposals.read_text())
    if LEFT not in {case['case_id'] for case in proposal['cases']}:
        selected = copy.deepcopy(proposal['cases'][0])
        selected['case_id'] = LEFT
        selected['rationale'] = 'Other approaches from ego left; synthetic CPU diagnostic only'
        proposal['cases'].append(selected)
        proposals.write_text(dump(proposal))
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for index in (0, 1, 2):
        ids = plan['requirement_dispositions'][index]['case_ids']
        if LEFT not in ids:
            ids.append(LEFT)
    plan_path.write_text(dump(plan))
    contract = copy.deepcopy(json.loads((ROOT / 'measurement-contract.json').read_text()))
    contract['requirements'] = [row for row in contract['requirements'] if row['disposition_index'] in (0, 1, 2)]
    contract['negative'] = {'remove': ['crossing_history.jsonl'],
                            'error_contains': 'Missing required source: crossing_history.jsonl'}
    (OUT / 'measurement-contract.json').write_text(dump(contract))
    manifest = json.loads(manifest_path.read_text())
    next(entry for entry in manifest['cases'] if entry['case_id'] == LEFT)['measurement_contract'] = str(
        (OUT / 'measurement-contract.json').relative_to(ROOT))
    manifest_path.write_text(dump(manifest))
    print(json.dumps({'case_id': LEFT, 'construction_sha256': sha(ctext),
                      'diagnostic_sha256': hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    build()
