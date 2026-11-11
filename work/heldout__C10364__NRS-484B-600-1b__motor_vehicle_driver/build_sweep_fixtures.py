"""Distinct marked synthetic originals for each authored alley offset point."""

from hashlib import sha256
import json
from pathlib import Path


root = Path(__file__).resolve().parent
repo = root.parents[1]
base = json.loads((root / 'diagnostic-person_3mps.json').read_text())
proposal = json.loads((root / 'proposals/cases.json').read_text())
manifest_path = root / 'probe-compatibility-manifest.json'
manifest = json.loads(manifest_path.read_text())
entries = {entry['case_id']: entry for entry in manifest['cases']}
for case in proposal['cases']:
    if case['target_type'] != 'judgment_sweep':
        continue
    case_id = case['case_id']
    suffix = case_id.split('__')[-1]
    offset = case['sweep_point']['pedestrian_offset_m']
    fixture = json.loads(json.dumps(base))
    rows = [json.loads(line) for line in fixture['files']['participant_footprints.jsonl'].splitlines()]
    for row in rows:
        row['pedestrian_corners'] = [[x, y + offset - 1.8]
                                     for x, y in row['pedestrian_corners']]
    fixture['files']['participant_footprints.jsonl'] = ''.join(
        json.dumps(row) + '\n' for row in rows)
    fixture['files']['fixture-provenance.json'] = json.dumps({
        'provenance_kind': 'synthetic_fixture',
        'scope': 'CPU diagnostic generated alley placement; no Native physical evidence',
        'source_case': 'C10364 diagnostic-person_3mps.json',
        'authored_pedestrian_offset_m': offset,
        'footprint_shift_y_m': offset - 1.8}) + '\n'
    path = root / ('diagnostic-' + suffix + '.json')
    path.write_text(json.dumps(fixture, separators=(',', ':')) + '\n')
    checksum = sha256(path.read_bytes()).hexdigest()
    reference = {'source': str(path.relative_to(repo)), 'sha256': checksum}
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [dict(reference, path='diagnostic-input.json')],
              'generator': reference}
    recipe_path = root / ('diagnostic-recipe-' + suffix + '.json')
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    entries[case_id]['fixture_recipe'] = str(recipe_path.relative_to(repo))
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print('Bound distinct synthetic original pedestrian footprints for three generated offset points')
