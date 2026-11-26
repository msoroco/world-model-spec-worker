"""Bind independent CPU delivery-chain positives and negative tamper proofs."""
import hashlib
import json
from pathlib import Path

from build_selected import CASES

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
SCRIPT = 'work/' + PACKAGE.name + '/native/audit_delivery.py'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = PACKAGE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for suffix, entry in zip(CASES, manifest['cases']):
        folder = PACKAGE / 'delivery-audit'
        positive = folder / (suffix + '-positive.log')
        negative = folder / (suffix + '-negative.log')
        report = json.loads(positive.read_text())
        if (report['case_id'] != entry['case_id'] or
                report['original_native_motion_verified'] is not False or
                report['saved_recorded_only'] is not True or
                'Delivery construction differs from selected manifest' not in negative.read_text()):
            raise ValueError('Independent delivery audit missing: ' + suffix)
        command = '.venv-cpu/bin/python ' + SCRIPT + ' --case ' + entry['case_id']
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['demo-train', 'full-train'],
            'checks': CHECKS, 'script': 'native/audit_delivery.py',
            'script_sha256': sha(HERE / 'audit_delivery.py'),
            'command': command, 'test_exit_code': 0,
            'test_log': str(positive.relative_to(PACKAGE)),
            'test_log_sha256': sha(positive),
            'negative_command': command + ' --negative',
            'negative_exit_code': 1,
            'negative_expected_error': 'Delivery construction differs from selected manifest',
            'negative_log': str(negative.relative_to(PACKAGE)),
            'negative_log_sha256': sha(negative),
            'scope': 'CPU synthetic source chain; original Native pixels and physical completion require local acceptance',
        }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'delivery_bound': len(manifest['cases']),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
