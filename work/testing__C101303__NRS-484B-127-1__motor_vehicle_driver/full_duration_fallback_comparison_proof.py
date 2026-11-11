"""Audit fallback construction isolation against full-length diagnostic originals.

The source histories are those of each primary diagnostic case. This exercises
the candidate configuration joins but does not assert fallback physical motion.
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


def source(case):
    label = case.rsplit('source_verified_', 1)[1]
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
    left, right = map(source, pairing['case_ids'])
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
                      'candidate_source_kind': 'primary_synthetic_diagnostic_reuse',
                      'physical_fallback_motion_proven': False}, sort_keys=True))
