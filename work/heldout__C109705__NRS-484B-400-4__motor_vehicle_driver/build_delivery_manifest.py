"""Bind existing exact turn proofs into one canonical delivery manifest."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROBE = HERE / 'probe-compatibility-manifest.json'
OUTPUT = HERE / 'execution-manifest.json'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def compatible_output(slug, candidate, expected):
    matches = []
    for path in (ROOT / '.runtime-work').glob(
            'c109705-candidate-' + slug + '-' + candidate + '-compatibility-v*'):
        receipt = path / 'compatibility.json'
        if receipt.is_file() and read(receipt) == expected:
            matches.append(path)
    if not matches:
        raise ValueError('Missing exact retained compatibility attempt: ' + slug + ' ' + candidate)
    return max(matches, key=lambda path: int(path.name.rsplit('-v', 1)[1]))


def main():
    if OUTPUT.exists():
        raise ValueError('Retain prior canonical delivery manifest')
    manifest = deepcopy(read(PROBE))
    manifest['format'] = 'worker-execution-manifest'
    records = {(row['case_id'], row['candidate_id']): row
               for row in read(HERE / 'candidate-proofs.json')}
    saved = {(row['case_id'], row['candidate_id']): row
             for row in read(HERE / 'saved-candidate-proofs.json')}
    physical = {row['case_id']: row for row in read(HERE / 'turn-physical-proofs.json')}
    delivery = {row['case_id']: row for row in read(HERE / 'turn-delivery-proofs.json')}
    for entry in manifest['cases']:
        case = entry['case_id']
        slug = case.split('__')[-1]
        for candidate, target in [('primary', entry)] + [
                (item['id'], item) for item in entry['candidates']]:
            row = records[case, candidate]
            if row['compatibility_receipt']['construction_sha256'] != target['construction_sha256']:
                raise ValueError('Turn construction/compatibility hash differs: ' + slug)
            offline_log = HERE / row['offline_log']
            if digest(offline_log) != row['offline_log_sha256']:
                raise ValueError('Turn offline log changed: ' + slug)
            target['offline'] = {
                'command': (str(ROOT / '.venv-cpu/bin/python') + ' runtime.py offline --manifest ' +
                            str(PROBE.relative_to(ROOT)) + ' --case ' + case +
                            ' --candidate ' + candidate + ' --python ' +
                            str(ROOT / '.venv-cpu/bin/python')),
                'exit_code': 0, 'log': row['offline_log'],
                'log_sha256': digest(offline_log),
                'construction_sha256': target['construction_sha256']}
            attempt = compatible_output(slug, candidate, row['compatibility_receipt'])
            names = {'compatibility.json': 'compat-' + slug + '-' + candidate + '.json',
                     'compatibility-analysis.log': 'compat-' + slug + '-' + candidate + '-analysis.log',
                     'negative-analysis.log': 'compat-' + slug + '-' + candidate + '-negative.log'}
            for source, dest in names.items():
                shutil.copy2(attempt / source, HERE / 'cases' / dest)
            receipt = HERE / 'cases' / names['compatibility.json']
            analysis = HERE / 'cases' / names['compatibility-analysis.log']
            negative = HERE / 'cases' / names['negative-analysis.log']
            if (digest(analysis) != row['compatibility_receipt']['log_sha256'] or
                    digest(negative) != row['compatibility_receipt']['negative_log_sha256']):
                raise ValueError('Turn compatibility source log differs: ' + slug)
            target['compatibility'] = {'receipt': str(receipt.relative_to(HERE)),
                                       'sha256': digest(receipt),
                                       'log': str(analysis.relative_to(HERE)),
                                       'negative_log': str(negative.relative_to(HERE))}
            if candidate == 'primary':
                entry['negative'] = {'log': str(negative.relative_to(HERE))}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        receipt = saved[case, 'primary']
        if digest(HERE / receipt['log']) != receipt['log_sha256']:
            raise ValueError('Turn saved-processing log changed: ' + slug)
        entry['post_capture'] = {
            'recorded_only': True,
            'command': ('.venv-cpu/bin/python runtime.py process-saved --manifest ' +
                        str(OUTPUT.relative_to(ROOT)) + ' --case ' + case +
                        ' --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT"' +
                        ' --library runtime/library --validator ' +
                        '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck'),
            'feedback_command': 'cat "$PROCESSING_OUTPUT/feedback.json"',
            'test_log': receipt['log'], 'test_log_sha256': digest(HERE / receipt['log']),
            'test_exit_code': 0}
        entry['physical_preparation'] = {key: value for key, value in
                                         physical[case].items() if key != 'case_id'}
        proof = delivery[case]
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['held-out'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'turn_delivery_audit.py',
            'script_sha256': proof['auditor_sha256'],
            'command': proof['positive_command'], 'test_exit_code': 0,
            'test_log': proof['positive_log'],
            'test_log_sha256': proof['positive_log_sha256'],
            'negative_command': proof['negative_command'],
            'negative_exit_code': proof['negative_exit_code'],
            'negative_expected_error': proof['negative_expected_error'],
            'negative_log': proof['negative_log'],
            'negative_log_sha256': proof['negative_log_sha256']}
    OUTPUT.write_text(json.dumps(manifest, indent=2) + '\n')
    print('six exact turn cases bound in canonical manifest:', digest(OUTPUT))


if __name__ == '__main__':
    main()
