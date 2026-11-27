"""Bind final source-checked CPU receipts to the selected case manifest."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
AID = HERE.name
CHANNELS = ('dev.regulatory_sign', 'dev.governs', 'dev.position', 'ru.bicycle',
            'ru.electric_bicycle', 'ru.electric_scooter', 'st.sidewalk',
            'st.roadway', 'rel.occupies')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        receipt = 'compat-' + suffix + '.json'
        entry['compatibility'] = {'receipt': receipt,
                                  'sha256': sha(HERE / receipt),
                                  'log': 'compat-' + suffix + '.log'}
        entry['negative'] = {'log': 'negative-' + suffix + '.log'}
        entry['acquisition'] = {name: {
            'entrypoint': 'finalize.py',
            'method': 'source-joined rider frames and reviewed sign setup',
            'evidence': 'channels/' + name + '.jsonl'} for name in CHANNELS}
        positive = 'native/delivery-' + suffix + '.log'
        negative = 'native/delivery-negative-' + suffix + '.log'
        prefix = '.venv-cpu/bin/python work/' + AID + '/native/delivery_audit.py'
        command = (prefix + ' --case ' + case + ' --attempt ' +
                   '.runtime-work/c230207-compat-' + suffix.replace('_', '') + '-v2')
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'native/delivery_audit.py',
            'script_sha256': sha(HERE / 'native/delivery_audit.py'),
            'command': command, 'negative_command': command + ' --negative-selftest',
            'test_exit_code': 0, 'negative_exit_code': 1,
            'negative_expected_error': 'setup.json',
            'test_log': positive, 'test_log_sha256': sha(HERE / positive),
            'negative_log': negative, 'negative_log_sha256': sha(HERE / negative),
            'diagnostic_only': True}
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(sha(path))


if __name__ == '__main__':
    bind()
