"""Bind 64 exact current-runtime long offline receipts to the partial selection."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
ARCHIVE = HERE / 'execution-manifest-current-short-only.json'
INDEX = HERE / 'current-selected-long-offline-index.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    index = json.loads(INDEX.read_text())
    runtime = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    original_sha = sha(MANIFEST)
    if (manifest['runtime_manifest_sha256'] != runtime or
            index['runtime_manifest_sha256'] != runtime or
            index['selected_manifest_sha256'] != original_sha or
            index['format'] != 'c150142-current-selected-long-offline-v1' or
            len(index['rows']) != 64 or
            manifest['delivery_ready'] is not False):
        raise ValueError('Current long offline index does not bind selected manifest')
    rows = {(row['case_id'], row['candidate_id']): row for row in index['rows']}
    if len(rows) != 64:
        raise ValueError('Duplicate current long offline candidate')
    cases = 0
    for entry in manifest['cases']:
        if entry.get('fixture_recipe'):
            continue
        cases += 1
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        fields = [('primary', entry)] + [(row['id'], row) for row in entry['candidates']]
        for candidate, field in fields:
            row = rows.pop((entry['case_id'], candidate))
            log = HERE / row['log']
            proof = json.loads(log.read_text())
            if (sha(log) != row['log_sha256'] or
                    row['construction_sha256'] != field['construction_sha256'] or
                    proof['case_id'] != entry['case_id'] or
                    proof['candidate_id'] != candidate or
                    proof['offline_passed'] is not True or
                    proof['simulation_started'] is not False):
                raise ValueError('Current long offline proof changed: ' + suffix + '/' + candidate)
            field['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest work/'
                           + HERE.name + '/execution-manifest.json --case '
                           + entry['case_id'] + ' --candidate ' + candidate,
                'exit_code': 0,
                'construction_sha256': field['construction_sha256'],
                'log': row['log'], 'log_sha256': row['log_sha256'],
                'manifest_sha256_at_execution': original_sha,
            }
    if cases != 16 or rows:
        raise ValueError('Long case inventory differs')
    if ARCHIVE.exists():
        if ARCHIVE.read_bytes() != MANIFEST.read_bytes():
            raise ValueError('Short-only archive differs')
    else:
        ARCHIVE.write_bytes(MANIFEST.read_bytes())
    manifest['status'] = 'selected_current_runtime_short_and_long_offline_public_pending'
    manifest['delivery_ready'] = False
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'long_cases': cases, 'long_candidates_offline': 64,
                      'selected_manifest_sha256': sha(MANIFEST),
                      'prior_selected_manifest_sha256': original_sha,
                      'delivery_ready': False}, indent=2))


if __name__ == '__main__':
    main()
