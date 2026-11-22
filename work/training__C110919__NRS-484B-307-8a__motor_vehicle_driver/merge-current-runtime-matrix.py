"""Merge the disjoint current-runtime candidate proof shards after completion."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GROUPS = (
    ('reference', 'contrast', 'absent_reference', 'absent_reference_contrast', 'green_release_wait'),
    ('green_release_red_turn', 'yield_wait', 'yield_conflict_entry', 'traffic_yield_wait', 'traffic_conflict_entry'),
    tuple(f'C110919-right-of-way-{i:04d}' for i in range(5)),
    tuple(f'C110919-extreme-right-{i:04d}' for i in range(5)),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = HERE / 'current-runtime-reproof-manifest.json'
    doc = json.loads(manifest.read_text())
    current = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    if doc['runtime_manifest_sha256'] != current:
        raise ValueError('Current runtime differs')
    rows = {}
    for group in GROUPS:
        progress = HERE / ('current-runtime-matrix-progress-' + '-'.join(sorted(group)) + '.json')
        part = json.loads(progress.read_text())
        if (part['runtime_manifest_sha256'] != current or
                part['manifest_sha256'] != sha(manifest) or
                part['completed'] != 4 * len(group)):
            raise ValueError('Matrix shard incomplete: ' + str(group))
        for row in part['rows']:
            key = (row['case_id'], row['candidate_id'])
            if key in rows:
                raise ValueError('Duplicate candidate chain: ' + str(key))
            folder = HERE / row['proof_dir']
            if (sha(folder / 'compatibility.json') != row['compatibility_sha256'] or
                    sha(folder / 'saved-processing.json') != row['saved_sha256']):
                raise ValueError('Retained candidate receipt changed: ' + str(key))
            rows[key] = row
    ordered = []
    for entry in doc['cases']:
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            ordered.append(rows[(entry['case_id'], candidate)])
    if len(ordered) != 80:
        raise ValueError('Eighty candidate chains required')
    merged = {'format': 'c110919-current-runtime-matrix-v1',
              'runtime_manifest_sha256': current, 'manifest_sha256': sha(manifest),
              'completed': 80, 'required': 80, 'rows': ordered}
    output = HERE / 'current-runtime-matrix-progress.json'
    output.write_text(json.dumps(merged, indent=2) + '\n')
    print(json.dumps({'completed': 80, 'sha256': sha(output)}))


if __name__ == '__main__':
    main()
