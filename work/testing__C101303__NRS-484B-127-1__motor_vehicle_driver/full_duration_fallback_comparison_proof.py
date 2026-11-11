"""Audit fallback construction isolation against candidate-bound CPU histories.

Fallback histories are synthetic projections of exact candidate knobs. They do
not assert realized Native motion or physical acceptance.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
sys.path.insert(0, str(folder))
from comparison_audit import audit_pair


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


projection = json.loads((folder / 'fallback-candidate-source-receipt.json').read_text())
if (projection.get('format') != 'worker-fallback-candidate-source-projections' or
        projection.get('physical_fallback_motion_proven') is not False or
        projection.get('generator_sha256') != sha(folder / 'fallback_candidate_sources.py')):
    raise ValueError('Fallback source generator receipt changed')
indexed = {(row['case_id'], row['candidate_id']): row for row in projection['sources']}
manifest = json.loads((folder / 'execution-manifest.json').read_text())


def source(case, candidate):
    label = case.rsplit('source_verified_', 1)[1]
    if candidate != 'primary':
        spec = indexed.get((case, candidate))
        entry = next(row for row in manifest['cases'] if row['case_id'] == case)
        selected = next(row for row in entry['candidates'] if row['id'] == candidate)
        if not spec or spec['construction_sha256'] != selected['construction_sha256']:
            raise ValueError('Fallback projection lacks selected construction: ' + case + '/' + candidate)
        def embedded_config(row):
            bundle = json.loads((folder / row['construction']).read_text())
            content = next(item['content'] for item in bundle['files'] if item['path'] == 'config.json')
            return json.loads(content)
        primary_config, candidate_config = embedded_config(entry), embedded_config(selected)
        changed_config = {key: value for key, value in candidate_config.items()
                          if primary_config.get(key) != value and
                          key not in ('selected_case_id', 'supported_case_ids')}
        recipe = json.loads((repo / entry['fixture_recipe']).read_text())
        if (spec['changed_config'] != changed_config or
                spec['source_specification'] != recipe['generator']['source']):
            raise ValueError('Fallback projection does not match exact candidate knobs')
        path = repo / spec['path']
        if (not path.is_file() or sha(path) != spec['sha256'] or spec['frames'] != 900 or
                sha(repo / spec['source_specification']) != spec['source_specification_sha256']):
            raise ValueError('Fallback projection source changed: ' + case + '/' + candidate)
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if len(rows) != 900 or any(row.get('diagnostic_projection') != {
                'candidate_id': candidate,
                'construction_sha256': selected['construction_sha256'],
                'changed_config': spec['changed_config'],
                'physical_motion_proven': False} for row in rows):
            raise ValueError('Fallback source lacks candidate-bound projection: ' + case + '/' + candidate)
        return path
    version = 'v2' if label == 'faster_ego' else 'v1'
    path = repo / '.runtime-work/c101303-full-duration' / (label + '-positive-' + version + '/attempt/vehicle_history.jsonl')
    receipt = json.loads((folder / 'delivery-proofs' / label / 'diagnostic-audit.json').read_text())
    if (receipt['frames'] != 900 or receipt['passed'] is not False or
            receipt['original_sources']['history_sha256'] != sha(path)):
        raise ValueError('Fallback proof lacks a current diagnostic original: ' + case)
    return path


rows = [json.loads(line) for line in (folder / 'all-comparison-audit.log').read_text().splitlines()]
pairings = [row for row in rows if (row['left_candidate'], row['right_candidate']) != ('primary', 'primary')]
if len(rows) != 28 or len(pairings) != 21 or Counter(row['comparison_id'] for row in pairings) != {
        key: 3 for key in ('body_gap', 'ego_speed', 'lead_speed', 'lead_braking',
                          'wet_surface', 'following_end', 'queued_traffic')}:
    raise ValueError('Expected all seven primary and 21 fallback pairing definitions')
seen = set()
for pairing in pairings:
    identity = (pairing['comparison_id'], pairing['left_candidate'], pairing['right_candidate'])
    if identity in seen:
        raise ValueError('Duplicate fallback pairing')
    seen.add(identity)
    left = source(pairing['case_ids'][0], pairing['left_candidate'])
    right = source(pairing['case_ids'][1], pairing['right_candidate'])
    result = audit_pair(folder, pairing['comparison_id'], left, right,
                        left_candidate=None if pairing['left_candidate'] == 'primary' else pairing['left_candidate'],
                        right_candidate=None if pairing['right_candidate'] == 'primary' else pairing['right_candidate'])
    if result['frames'] != 900 or result['changed_config_keys'] != pairing['changed_config_keys']:
        raise ValueError('Fallback comparison changed construction dimension or duration')
    print(json.dumps({'comparison_id': result['comparison_id'],
                      'left_candidate': result['left_candidate'],
                      'right_candidate': result['right_candidate'],
                      'frames': result['frames'],
                      'left_source_sha256': result['left_source_sha256'],
                      'right_source_sha256': result['right_source_sha256'],
                      'changed_config_keys': result['changed_config_keys'],
                      'observed_values_sha256': hashlib.sha256(json.dumps(result['observed_values']).encode()).hexdigest(),
                      'candidate_source_kind': 'candidate_bound_synthetic_projection',
                      'physical_fallback_motion_proven': False}, sort_keys=True))
