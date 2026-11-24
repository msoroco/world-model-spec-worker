"""Bind the 120 current-runtime Native offline receipts into a portable draft."""

import hashlib
import json
import os
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = ROOT / 'current-runtime-runner-draft-manifest.json'
INDEX = ROOT / 'current-runtime-runner-draft-offline-index.json'
TARGET = ROOT / 'current-runtime-runner-offline-bound-manifest.json'
RECEIPTS = ROOT / 'current-runtime-runner-offline'
SCRATCH = REPO / '.runtime-work/owner150142/offline-binding'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=SCRATCH,
                                     prefix='binding-', delete=False) as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')
        temporary = Path(stream.name)
    os.replace(temporary, path)


def run():
    manifest = json.loads(SOURCE.read_text(encoding='utf-8'))
    index = json.loads(INDEX.read_text(encoding='utf-8'))
    if index.get('passed') is not True or index.get('manifest_sha256') != sha(SOURCE):
        raise ValueError('Current offline index does not bind the draft manifest')
    rows = {(row['case_id'], row['candidate_id']): row for row in index['rows']}
    if len(rows) != 120 or index.get('candidates') != 120:
        raise ValueError('Current offline index does not cover 120 exact candidates')
    bound = []
    for entry in manifest['cases']:
        slug = entry['case_id'].removeprefix(ROOT.name + '__')
        for candidate_id, field in [('primary', entry),
                                    *[(item['id'], item) for item in entry['candidates']]]:
            key = (entry['case_id'], candidate_id)
            row = rows.pop(key)
            source_log = REPO / row['log']
            if row['exit_code'] != 0 or sha(source_log) != row['log_sha256']:
                raise ValueError('Changed current offline log for ' + repr(key))
            if field['construction_sha256'] != sha(ROOT / field['construction']):
                raise ValueError('Changed current construction for ' + repr(key))
            result = json.loads(source_log.read_text(encoding='utf-8'))
            if (result.get('case_id') != entry['case_id'] or
                    result.get('candidate_id') != candidate_id or
                    result.get('offline_passed') is not True or
                    result.get('simulation_started') is not False):
                raise ValueError('Current offline output does not prove candidate ' + repr(key))
            portable = RECEIPTS / slug / (candidate_id + '.log')
            portable.parent.mkdir(parents=True, exist_ok=True)
            if portable.exists():
                if sha(portable) != row['log_sha256']:
                    raise ValueError('Existing portable offline receipt changed: ' + str(portable))
            else:
                SCRATCH.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode='wb', dir=SCRATCH,
                                                 prefix='offline-', delete=False) as stream:
                    stream.write(source_log.read_bytes())
                    temporary = Path(stream.name)
                os.replace(temporary, portable)
            relative = str(portable.relative_to(ROOT))
            field['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                           + str(SOURCE.relative_to(REPO)) + ' --case '
                           + entry['case_id'] + ' --candidate ' + candidate_id
                           + ' --output ' + str((REPO / row['log']).parent / 'bundle'),
                'construction_sha256': field['construction_sha256'],
                'exit_code': 0,
                'log': relative,
                'log_sha256': sha(portable),
            }
            bound.append({'case_id': entry['case_id'], 'candidate_id': candidate_id,
                          'construction_sha256': field['construction_sha256'],
                          'log': relative, 'log_sha256': sha(portable)})
    if rows or len(bound) != 120:
        raise ValueError('Unbound current offline index rows')
    manifest['status'] = 'draft_current_runtime_offline_bound'
    manifest['delivery_ready'] = False
    write_json(TARGET, manifest)
    receipt = {'format': 'c150142-current-runtime-offline-binding-v1',
               'passed': True, 'source_manifest_sha256': sha(SOURCE),
               'offline_index_sha256': sha(INDEX),
               'bound_manifest_sha256': sha(TARGET),
               'cases': len(manifest['cases']), 'candidates': len(bound),
               'rows': bound, 'original_native_observed': False,
               'delivery_ready': False}
    write_json(ROOT / 'current-runtime-runner-offline-binding.json', receipt)
    return {'cases': receipt['cases'], 'candidates': receipt['candidates'],
            'manifest_sha256': receipt['bound_manifest_sha256']}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
