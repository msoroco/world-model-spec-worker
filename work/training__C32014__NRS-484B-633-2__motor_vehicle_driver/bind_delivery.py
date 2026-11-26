"""Bind exact CPU saved and independent delivery proofs to the selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[1]
        proof = 'proof/' + suffix + '/'
        saved_log = proof + 'saved-final.log'
        positive_log = proof + 'delivery-positive.log'
        negative_log = proof + 'delivery-negative.log'
        entry['delivery_readiness'] = 'cpu_prepared_native_authority_and_pixels_pending'
        entry['post_capture'] = {
            'recorded_only': True,
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + HERE.name +
                       '/execution-manifest.json --case ' + case +
                       ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library'
                       ' --validator $DECODER --owner-release-receipt $ATTEMPT/owner-release.json',
            'feedback_command': 'cat $SAVED_OUTPUT/v0001/feedback.json # ' + case,
            'test_exit_code': 0,
            'test_log': saved_log,
            'test_log_sha256': sha(HERE / saved_log),
        }
        entry['delivery_acceptance'] = {
            'case_id': case,
            'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion', 'department_source',
                       'bridge_mesh_and_both_sign_faces', 'actual_on_structure_speed'],
            'script': 'delivery_audit.py',
            'script_sha256': sha(HERE / 'delivery_audit.py'),
            'command': '.venv-cpu/bin/python work/' + HERE.name +
                       '/delivery_audit.py --case ' + case +
                       ' --processing $PROCESSING --output $AUDIT_OUTPUT',
            'test_exit_code': 0,
            'test_log': positive_log,
            'test_log_sha256': sha(HERE / positive_log),
            'negative_command': '.venv-cpu/bin/python work/' + HERE.name +
                                '/delivery_audit.py --case ' + case +
                                ' --processing $PROCESSING --output $AUDIT_OUTPUT'
                                ' --diagnostic --omit-source bridge-speed-history.jsonl',
            'negative_exit_code': 1,
            'negative_expected_error': 'Missing original delivery source: bridge-speed-history.jsonl',
            'negative_log': negative_log,
            'negative_log_sha256': sha(HERE / negative_log),
            'diagnostic_only_test': True,
            'authority_negative_log': 'proof/authority-negative.log',
            'authority_negative_log_sha256': sha(HERE / 'proof/authority-negative.log'),
        }
    write(MANIFEST, manifest)


if __name__ == '__main__':
    main()
