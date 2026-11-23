"""Bind tested selected receipts and delivery-audit contracts into the manifest."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OLD_MANIFEST_SHA = '13cb0a83962c40d73d1a8a990c2ce08569e25a874418b9d8dde1edf25f8ff102'
GROUPS = ('reference', 'contrast', 'conflict', 'clear', 'near_lead',
          'absent_lead', 'device_direction', 'officer_direction')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    path = HERE / 'execution-manifest.json'
    require(sha(path) == OLD_MANIFEST_SHA, 'Expected selected manifest differs')
    manifest = json.loads(path.read_text())
    require({row['case_id'] for row in manifest['cases']} ==
            {HERE.name + '__' + group for group in GROUPS},
            'Selected case coverage differs')
    script = HERE / 'delivery_audit.py'
    for entry in manifest['cases']:
        group = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in [entry, *entry['candidates']]:
            candidate_id = 'primary' if candidate is entry else candidate['id']
            prefix = 'selected-' + group + '-' + candidate_id
            offline_name = prefix + ('-offline-v2.log'
                                     if group == 'reference' and candidate_id == 'primary'
                                     else '-offline.log')
            offline_path = HERE / offline_name
            compat_name = prefix + '-compatibility.log'
            analysis_name = prefix + '-analysis.log'
            negative_name = prefix + '-negative-analysis.log'
            saved_name = prefix + '-saved.log'
            require(all((HERE / name).is_file() for name in
                        (offline_name, compat_name, analysis_name,
                         negative_name, saved_name)),
                    'Selected receipt missing: ' + prefix)
            output = '.runtime-work/c201084-' + prefix + '-offline'
            if group == 'reference' and candidate_id == 'primary':
                output += '-v2'
            candidate['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' +
                           HERE.name + '/execution-manifest.json --case ' +
                           entry['case_id'] + ' --candidate ' + candidate_id +
                           ' --output ' + output,
                'construction_sha256': candidate['construction_sha256'],
                'exit_code': 0, 'log': offline_name,
                'log_sha256': sha(offline_path),
            }
            candidate['compatibility'] = {
                'log': analysis_name,
                'negative_log': negative_name,
                'receipt': compat_name,
                'sha256': sha(HERE / compat_name),
            }
            candidate['negative'] = {'log': negative_name}
            candidate['saved_processing'] = {
                'receipt': saved_name,
                'sha256': sha(HERE / saved_name),
            }
        proof = HERE / 'delivery-proofs' / group
        pos_log = proof / 'positive.log'
        neg_log = proof / 'negative.log'
        require(pos_log.is_file() and neg_log.is_file() and
                'Original Native source required' in neg_log.read_text(),
                'Delivery audit logs missing: ' + group)
        attempt = REPO / '.runtime-work' / ('c201084-final-' + group + '-primary-compatibility')
        processing = REPO / '.runtime-work' / ('c201084-final-' + group + '-primary-saved/v0001/processing.json')
        output = proof / 'positive.json'
        rejected = proof / 'rejected.json'
        common = (str(REPO / '.venv-cpu/bin/python') + ' ' + str(script) +
                  ' --case ' + entry['case_id'] + ' --candidate primary' +
                  ' --attempt ' + str(attempt) +
                  ' --processing ' + str(processing))
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'],
            'checks': list(CHECKS), 'script': 'delivery_audit.py',
            'script_sha256': sha(script),
            'command': common + ' --output ' + str(output) + ' --diagnostic',
            'test_exit_code': 0,
            'test_log': str(pos_log.relative_to(HERE)),
            'test_log_sha256': sha(pos_log),
            'negative_command': common + ' --output ' + str(rejected),
            'negative_exit_code': 1,
            'negative_expected_error': 'Original Native source required',
            'negative_log': str(neg_log.relative_to(HERE)),
            'negative_log_sha256': sha(neg_log),
            'proof_scope': 'Synthetic diagnostic positive and original-source rejection; no physical acceptance',
        }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
