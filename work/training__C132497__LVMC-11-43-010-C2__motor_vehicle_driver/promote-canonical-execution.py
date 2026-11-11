"""Activate source-bound CPU candidate bindings without claiming delivery readiness."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    draft = ROOT/'canonical-execution-draft.json'
    manifest = ROOT/'execution-manifest.json'
    data = json.loads(draft.read_text())
    assert data['format'] == 'worker-execution-manifest'
    assert data['original_native_observed'] is False and data['delivery_ready'] is False
    assert len(data['cases']) == 2
    assert all(len(case['candidates']) == 3 and case['offline']['exit_code'] == 0
               for case in data['cases'])
    manifest.write_text(draft.read_text())
    index_path = ROOT/'update015-current-candidate-index.json'
    index = json.loads(index_path.read_text())
    count = 0
    for row in index['results']:
        if row['candidate_id'] == 'primary':
            assert row['manifest'] == manifest.name
            row['manifest_sha256'] = sha(manifest)
            count += 1
    assert count == 2
    index_path.write_text(json.dumps(index, indent=2)+'\n')
    print(json.dumps({'active_manifest_sha256':sha(manifest),
                      'index_sha256':sha(index_path),
                      'primary_index_rows_updated':count,
                      'delivery_ready':False}))


if __name__ == '__main__':
    main()
