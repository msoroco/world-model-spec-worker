"""Bind passing recorded-only saved-processing diagnostics for each candidate."""

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = BASE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for side, entry in zip('ab', manifest['cases']):
        for candidate, selected in [('primary', entry), ('fallback1', entry['candidates'][0])]:
            original = ROOT / f'.runtime-work/c230259-297-2-saved-{side}-{candidate}-final/v0001/processing.json'
            receipt = json.loads(original.read_text())
            if (receipt['passed'] is not True or receipt['recorded_only'] is not True or
                    receipt['originals_preserved'] is not True or receipt['missing_evidence'] is not False or
                    receipt['case_id'] != entry['case_id'] or receipt['candidate_id'] != candidate or
                    receipt['analysis_revision']['construction_sha256'] != selected['construction_sha256']):
                raise ValueError('Saved processing receipt did not preserve selected source/candidate')
            destination = BASE / f'selected-proofs/{side}-{candidate}-saved.json'
            write(destination, receipt)
            selected['saved_processing'] = {'receipt': str(destination.relative_to(BASE)),
                                            'sha256': sha(destination)}
            if candidate == 'primary':
                command = ('.venv-cpu/bin/python -B runtime.py process-saved '
                           f'--manifest work/{BASE.name}/execution-manifest.json '
                           f'--case {entry["case_id"]} --attempt "$SAVED_ATTEMPT" '
                           '--output "$PROCESSED_OUT" --library runtime/library '
                           '--validator "$DECODER" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
                entry['post_capture'] = {
                    'recorded_only': True, 'command': command,
                    'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
                    'test_exit_code': 0, 'test_log': str(destination.relative_to(BASE)),
                    'test_log_sha256': sha(destination),
                }
    write(manifest_path, manifest)
    print(json.dumps({'saved_cases_bound': [entry['case_id'] for entry in manifest['cases']]}))


if __name__ == '__main__':
    main()
