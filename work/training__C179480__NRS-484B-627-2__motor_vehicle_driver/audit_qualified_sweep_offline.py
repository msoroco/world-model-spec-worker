"""Independently bind all qualified sweep offline logs to current constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest_path = HERE / 'sweep-candidate-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    index = json.loads((HERE / 'sweep-qualified-offline-index.json').read_text())
    if (len(manifest['cases']) != 9 or index['manifest_sha256'] != sha(manifest_path)
            or index['count'] != 36 or len(index['rows']) != 36):
        raise ValueError('Exact qualified sweep matrix is incomplete')
    expected = set()
    for entry in manifest['cases']:
        cid = entry['case_id']
        if not cid.startswith(HERE.name + '__c179480-'):
            raise ValueError('Sweep execution ID is not assignment-qualified')
        candidates = [('primary', entry)] + [(item['id'], item) for item in entry['candidates']]
        if len(candidates) != 4:
            raise ValueError('Three fallbacks required')
        hashes = set()
        for name, candidate in candidates:
            key = (cid, name)
            if key in expected:
                raise ValueError('Duplicate case/candidate')
            expected.add(key)
            construction = HERE / candidate['construction']
            if sha(construction) != candidate['construction_sha256']:
                raise ValueError('Construction changed: ' + cid + '/' + name)
            hashes.add(candidate['construction_sha256'])
            log = HERE / f'sweep-qualified-{cid}-{name}-offline.log'
            receipt = json.loads(log.read_text())
            if (not receipt['offline_passed'] or receipt['case_id'] != cid
                    or receipt['candidate_id'] != name or receipt['simulation_started']):
                raise ValueError('Offline proof failed: ' + cid + '/' + name)
            matching = [row for row in index['rows'] if
                        (row['case_id'], row['candidate']) == key]
            if (len(matching) != 1 or matching[0]['log_sha256'] != sha(log)
                    or matching[0]['construction_sha256'] != candidate['construction_sha256']):
                raise ValueError('Offline index differs: ' + cid + '/' + name)
        if len(hashes) != 4:
            raise ValueError('Fallback construction is not distinct: ' + cid)
    if expected != {(row['case_id'], row['candidate']) for row in index['rows']}:
        raise ValueError('Offline index has extra or missing cases')
    return {'format': 'c179480-qualified-sweep-offline-audit-v1', 'passed': True,
            'case_count': 9, 'candidate_count': 36,
            'candidate_manifest_sha256': sha(manifest_path),
            'offline_index_sha256': sha(HERE / 'sweep-qualified-offline-index.json'),
            'selected_cases': 0, 'native_observed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, sort_keys=True))
