"""Retain exact current-runtime public and saved CPU receipts for three cases."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
SCRATCH = ROOT / '.runtime-work/c111334-resume'
SUFFIXES = ('probe_1', 'probe_2', 'permission_before_entry')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def save_log(path, content):
    lines = [line.rstrip() for line in content.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    path.write_text('\n'.join(lines) + '\n')


def bind():
    manifest = PACKAGE / 'native-draft-manifest.json'
    manifest_data = json.loads(manifest.read_text())
    by_case = {entry['case_id']: entry for entry in manifest_data['cases']}
    for suffix in SUFFIXES:
        case_id = PACKAGE.name + '__' + suffix
        entry = by_case[case_id]
        dest = PACKAGE / 'native-selected' / suffix
        compat = SCRATCH / ('compat-' + suffix + '-v8')
        positive = SCRATCH / ('saved-' + suffix + '-positive-output-v8/v0001')
        negative = SCRATCH / ('saved-' + suffix + '-negative-output-v8/v0001')
        compatibility = json.loads((compat / 'compatibility.json').read_text())
        processing = json.loads((positive / 'processing.json').read_text())
        feedback = json.loads((negative / 'feedback.json').read_text())
        assert compatibility['passed'] is True
        assert compatibility['case_id'] == case_id
        assert compatibility['construction_sha256'] == entry['construction_sha256']
        assert {'selected_measurements', 'negative_case_source', 'final_decode',
                'lean_decoder', 'four_camera_sources'} <= set(compatibility['checks'])
        assert processing['passed'] is True and processing['missing_evidence'] is False
        assert processing['physical_acceptance_claimed'] is False
        assert 'Missing required source: device-review.json' in feedback['error']
        files = {
            'primary-compatibility.json': compatibility,
            'saved-positive-processing.json': processing,
            'saved-negative-feedback.json': feedback,
        }
        for name, value in files.items():
            save_json(dest / name, value)
        logs = {
            'primary-compatibility-analysis.log': compat / 'compatibility-analysis.log',
            'primary-negative-analysis.log': compat / 'negative-analysis.log',
            'saved-positive-analysis.log': positive / 'analysis.log',
            'saved-negative-analysis.log': negative / 'analysis.log',
        }
        for name, source in logs.items():
            save_log(dest / name, source.read_text())
        paths = sorted((*files, *logs))
        receipt = {
            'format': 'c111334-public-saved-case-proof-v2',
            'case_id': case_id,
            'manifest_sha256': sha(manifest),
            'construction_sha256': entry['construction_sha256'],
            'compatibility_passed': True,
            'saved_positive_passed': True,
            'saved_negative_missing_device_review': True,
            'original_native_observed': False,
            'physical_acceptance_claimed': False,
            'files': {name: {'path': str((dest / name).relative_to(PACKAGE)),
                             'sha256': sha(dest / name)} for name in paths},
        }
        save_json(dest / 'public-saved-proof.json', receipt)
    return {'cases': len(SUFFIXES), 'manifest_sha256': sha(manifest)}


if __name__ == '__main__':
    print(json.dumps(bind(), sort_keys=True))
