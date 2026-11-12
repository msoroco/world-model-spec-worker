"""Propagate reviewed operative head ordering into the exact construction."""
import json
from pathlib import Path

from build_operative_case import HERE, OUT, CASE, sha, variant_sources


def refresh():
    root = json.loads((HERE / 'construction.json').read_text())
    original = {item['path']: item['content'] for item in root['files']}
    variants = variant_sources(original)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    construction_path = HERE / entry['construction']
    construction = json.loads(construction_path.read_text())
    for item in construction['files']:
        if item['path'] in variants:
            item['content'] = variants[item['path']]
            (OUT / item['path']).write_text(item['content'])
    construction_path.write_text(json.dumps(construction, indent=2, allow_nan=False) + '\n')
    entry['construction_sha256'] = sha(construction_path)
    for key in ('offline', 'compatibility', 'negative'):
        entry.pop(key, None)
    manifest['status'] = 'partial_four_case_operative_reproof_pending'
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return entry['construction_sha256']


if __name__ == '__main__':
    print(refresh())
