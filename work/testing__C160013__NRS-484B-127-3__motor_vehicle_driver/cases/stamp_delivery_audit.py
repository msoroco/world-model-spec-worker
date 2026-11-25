"""Bind the independent positive and changed-source CPU delivery proofs."""
import hashlib
import json
import shutil
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
manifest_path = PACKAGE / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for label, suffix in (('wide', 'entrant_can_occupy_gap'),
                      ('narrow', 'entrant_cannot_occupy_gap')):
    entry = next(row for row in manifest['cases'] if row['case_id'].endswith('__' + suffix))
    positive = REPO / '.runtime-work' / ('c160013-' + label + '-delivery-positive.log')
    negative = REPO / '.runtime-work' / ('c160013-' + label + '-delivery-negative.log')
    passed = json.loads(positive.read_text())
    if (passed.get('case_id') != entry['case_id'] or passed.get('diagnostic_audit_passed') is not True
            or passed.get('joined_frames') != 900 or len(passed.get('camera_decodes', {})) != 4
            or 'Changed original source hash' not in negative.read_text()):
        raise ValueError('Independent delivery proof incomplete: ' + suffix)
    positive_out = PACKAGE / 'cases' / (suffix + '-delivery-positive.log')
    negative_out = PACKAGE / 'cases' / (suffix + '-delivery-negative.log')
    shutil.copyfile(positive, positive_out)
    shutil.copyfile(negative, negative_out)
    command = '.venv-cpu/bin/python work/' + PACKAGE.name + '/delivery_audit.py --case ' + entry['case_id'] + \
              ' --attempt .runtime-work/c160013-' + label + '-saved-v2/v0001/analysis'
    entry['delivery_acceptance'] = {
        'case_id': entry['case_id'], 'sets': ['demo-test', 'full-test'],
        'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                   'actual_pixels', 'physical_completion'],
        'script': 'delivery_audit.py', 'script_sha256': sha(PACKAGE / 'delivery_audit.py'),
        'command': command + ' --mode positive', 'test_exit_code': 0,
        'test_log': 'cases/' + positive_out.name, 'test_log_sha256': sha(positive_out),
        'negative_command': command + ' --mode negative', 'negative_exit_code': 1,
        'negative_expected_error': 'Changed original source hash',
        'negative_log': 'cases/' + negative_out.name, 'negative_log_sha256': sha(negative_out),
        'scope': 'diagnostic CPU boundary; native source, actual pixels, and physical owner acceptance pending'}

manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print('Bound both exact-case diagnostic delivery audit proofs')
