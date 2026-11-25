"""Select current-runtime short proofs while preserving long CPU proof gaps."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CURRENT = HERE / 'execution-manifest.json'
SOURCE = HERE / 'current-runtime-refresh-short-all-bound-manifest.json'
ARCHIVE = HERE / 'execution-manifest-previous-runtime-selected.json'
SHORTS = {
    'reference', 'contrast', 'ordinary_red_signed',
    'armored_car_signed_business', 'armored_car_signed_no_business',
    'armored_car_unsigned_business', 'armored_car_unsigned_no_business',
    'emergency_vehicle_signed_business', 'emergency_vehicle_signed_no_business',
    'emergency_vehicle_unsigned_business', 'emergency_vehicle_unsigned_no_business',
    'mail_adjacent_deposit', 'mail_adjacent_no_deposit', 'mail_no_box_deposit',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old = json.loads(CURRENT.read_text())
    proposed = json.loads(SOURCE.read_text())
    runtime = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    old_cases = {row['case_id']: row for row in old['cases']}
    new_cases = {row['case_id']: row for row in proposed['cases']}
    if (len(old_cases) != 30 or len(new_cases) != 30 or
            set(old_cases) != set(new_cases) or
            old['assignment_id'] != HERE.name or
            proposed['assignment_id'] != HERE.name or
            proposed['runtime_manifest_sha256'] != runtime or
            old['case_plan_sha256'] != proposed['case_plan_sha256'] or
            old['selection_source_sha256'] != proposed['selection_source_sha256'] or
            old['selected_branch'] != proposed['selected_branch'] or
            proposed.get('delivery_ready') is not False):
        raise ValueError('Selected identity or runtime binding differs')
    selected = 0
    pending = 0
    for case_id, entry in new_cases.items():
        suffix = case_id.removeprefix(HERE.name + '__')
        if sha(HERE / entry['construction']) != entry['construction_sha256']:
            raise ValueError('Current construction changed: ' + suffix)
        if suffix in SHORTS:
            selected += 1
            fields = [('primary', entry)] + [(c['id'], c) for c in entry['candidates']]
            if len(fields) != 4:
                raise ValueError('Short candidate count changed: ' + suffix)
            for candidate, field in fields:
                offline = field['offline']
                if (offline['construction_sha256'] != field['construction_sha256'] or
                        offline['exit_code'] != 0 or
                        sha(HERE / offline['log']) != offline['log_sha256']):
                    raise ValueError('Short offline binding differs: ' + suffix + '/' + candidate)
                if candidate == 'primary':
                    compatibility = field['compatibility']
                else:
                    compatibility = field['compatibility']
                receipt = HERE / compatibility['receipt']
                proof = json.loads(receipt.read_text())
                if (sha(receipt) != compatibility['sha256'] or
                        proof['case_id'] != case_id or
                        proof['candidate_id'] != candidate or
                        proof['construction_sha256'] != field['construction_sha256'] or
                        proof['runtime_manifest_sha256'] != runtime or
                        proof['passed'] is not True):
                    raise ValueError('Short public binding differs: ' + suffix + '/' + candidate)
        else:
            pending += 1
            if entry.get('compatibility') or any(c.get('compatibility') for c in entry['candidates']):
                raise ValueError('Unexpected long public proof: ' + suffix)
    if selected != 14 or pending != 16:
        raise ValueError('Short/long selected partition differs')
    if ARCHIVE.exists():
        if ARCHIVE.read_bytes() != CURRENT.read_bytes():
            raise ValueError('Prior selected manifest archive differs')
    else:
        ARCHIVE.write_bytes(CURRENT.read_bytes())
    proposed['status'] = 'selected_current_runtime_short_proven_long_pending'
    proposed['delivery_ready'] = False
    proposed['original_native_observed'] = False
    CURRENT.write_text(json.dumps(proposed, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'selected_manifest_sha256': sha(CURRENT),
                      'previous_manifest_sha256': sha(ARCHIVE),
                      'current_runtime_sha256': runtime,
                      'short_cases_with_fresh_offline_and_public': selected,
                      'long_cases_public_pending': pending,
                      'delivery_ready': False}, indent=2))


if __name__ == '__main__':
    main()
