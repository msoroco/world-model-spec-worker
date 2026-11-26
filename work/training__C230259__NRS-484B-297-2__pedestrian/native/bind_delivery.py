"""Bind the independent positive and original-source-negative CPU audit checks."""

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_clean(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source.read_text().rstrip() + '\n')
    return sha(destination)


def command(side, diagnostic):
    case = f'{BASE.name}__selected_81846e7f__condition_{side}'
    return (f'.venv-cpu/bin/python -B work/{BASE.name}/delivery_audit.py '
            f'--case {case} --candidate primary '
            f'--attempt .runtime-work/c230259-297-2-saved-source-{side}-primary-final '
            f'--processing work/{BASE.name}/selected-proofs/{side}-primary-saved.json '
            f'--output .runtime-work/c230259-297-2-delivery-{side}-primary-final.json' +
            (' --diagnostic' if diagnostic else ''))


def main():
    manifest_path = BASE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for side, entry in zip('ab', manifest['cases']):
        positive = ROOT / f'.runtime-work/c230259-297-2-delivery-{side}-primary-final.log'
        negative = ROOT / f'.runtime-work/c230259-297-2-delivery-{side}-primary-negative.log'
        proof = json.loads((ROOT / f'.runtime-work/c230259-297-2-delivery-{side}-primary-final.json').read_text())
        if not proof['passed'] or proof['case_id'] != entry['case_id'] or not proof['diagnostic']:
            raise ValueError('Positive delivery audit differs')
        if 'Original Native source required' not in negative.read_text():
            raise ValueError('Negative delivery audit did not reject synthetic original')
        positive_out = BASE / f'delivery-proofs/{side}-diagnostic.log'
        negative_out = BASE / f'delivery-proofs/{side}-original-required.log'
        copy_clean(positive, positive_out)
        copy_clean(negative, negative_out)
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'], 'checks': CHECKS,
            'script': 'delivery_audit.py', 'script_sha256': sha(BASE / 'delivery_audit.py'),
            'command': command(side, True), 'test_exit_code': 0,
            'test_log': str(positive_out.relative_to(BASE)), 'test_log_sha256': sha(positive_out),
            'negative_command': command(side, False), 'negative_exit_code': 1,
            'negative_expected_error': 'Original Native source required',
            'negative_log': str(negative_out.relative_to(BASE)),
            'negative_log_sha256': sha(negative_out),
        }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'delivery_cases_bound': [entry['case_id'] for entry in manifest['cases']]}))


if __name__ == '__main__':
    main()
