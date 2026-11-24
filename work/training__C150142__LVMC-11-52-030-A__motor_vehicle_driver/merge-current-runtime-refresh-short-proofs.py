"""Merge independently verified fresh short offline and public proof bindings."""

import hashlib
import json
import os
from pathlib import Path
import tempfile


WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
SOURCE = WORK / 'current-runtime-refresh-short-bound-manifest.json'
INDEX = WORK / 'current-runtime-refresh-short-offline-index.json'
TARGET = WORK / 'current-runtime-refresh-short-all-bound-manifest.json'
TEMP = REPO / '.runtime-work/owner150142/runtime-refresh-merge'
SHORTS = {'reference', 'contrast', 'ordinary_red_signed',
          'armored_car_signed_business', 'armored_car_signed_no_business',
          'armored_car_unsigned_business', 'armored_car_unsigned_no_business',
          'emergency_vehicle_signed_business',
          'emergency_vehicle_signed_no_business',
          'emergency_vehicle_unsigned_business',
          'emergency_vehicle_unsigned_no_business',
          'mail_adjacent_deposit', 'mail_adjacent_no_deposit',
          'mail_no_box_deposit'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    manifest = json.loads(SOURCE.read_text())
    index = json.loads(INDEX.read_text())
    original = WORK / 'current-runtime-refresh-short-draft-manifest.json'
    current = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    if (manifest['runtime_manifest_sha256'] != current or
            index['runtime_manifest_sha256'] != current or
            index['manifest_sha256'] != sha(original) or
            index['completed'] != 56 or index['expected'] != 56):
        raise ValueError('Fresh offline/public proof inventory is incomplete or stale')
    rows = {(row['case_id'], row['candidate_id']): row for row in index['rows']}
    if len(rows) != 56:
        raise ValueError('Duplicate or missing short offline candidate')
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(WORK.name + '__')
        if suffix not in SHORTS:
            continue
        fields = [('primary', entry)] + [(item['id'], item) for item in entry['candidates']]
        for candidate, field in fields:
            row = rows.pop((entry['case_id'], candidate))
            log = WORK / row['log']
            proof = json.loads(log.read_text())
            if (row['construction_sha256'] != field['construction_sha256'] or
                    sha(log) != row['log_sha256'] or
                    proof['case_id'] != entry['case_id'] or
                    proof['candidate_id'] != candidate or
                    proof['offline_passed'] is not True or
                    proof['simulation_started'] is not False):
                raise ValueError('Fresh offline candidate binding failed: ' + suffix + '/' + candidate)
            field['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                           + str(original.relative_to(REPO)) + ' --case '
                           + entry['case_id'] + ' --candidate ' + candidate
                           + ' --output .runtime-work/owner150142/runtime-refresh-short-offline/'
                           + suffix + '/' + candidate,
                'construction_sha256': field['construction_sha256'],
                'exit_code': 0, 'log': row['log'],
                'log_sha256': row['log_sha256'],
            }
    if rows:
        raise ValueError('Unbound short offline candidate rows')
    manifest['status'] = 'draft_current_runtime_refresh_short_all_bound'
    manifest['delivery_ready'] = False
    TEMP.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                     dir=TEMP, delete=False) as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2)
        stream.write('\n')
        temporary = Path(stream.name)
    os.replace(temporary, TARGET)
    return {'short_cases': 14, 'fresh_short_offline': 56,
            'fresh_short_public': 56,
            'runtime_manifest_sha256': current,
            'manifest_sha256': sha(TARGET), 'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
