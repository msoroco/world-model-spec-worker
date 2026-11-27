"""Exercise independent original-delivery predicates for device pair identities."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
PROBES = ('device_dim', 'device_high')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for probe in PROBES:
    case = AID+'__'+probe
    tests = {}
    for kind in ('positive', 'negative'):
        command = [str(REPO/'.venv-cpu/bin/python'), '-B', str(ROOT/'delivery_audit.py'),
                   '--case', case, '--self-test']
        if kind == 'negative':
            command.append('--negative')
        result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        log = ROOT/'native'/f'delivery-{probe}-{kind}.log'
        log.write_text(result.stdout+result.stderr)
        if result.returncode != (0 if kind == 'positive' else 1):
            raise RuntimeError(f'{probe} {kind}: {result.stderr[-1000:]}')
        if kind == 'negative' and 'Missing exact original Native beam result' not in log.read_text():
            raise ValueError('Missing-source negative auditor did not reject')
        tests[kind] = {'command': ' '.join(command), 'exit_code': result.returncode,
                       'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log)}
    receipt = {'case_id': case, 'sets': ['full-train'],
               'checks': ['native_source', 'all_participants', 'time_join',
                          'full_video_decode', 'actual_pixels', 'physical_completion'],
               'script': 'delivery_audit.py', 'script_sha256': sha(ROOT/'delivery_audit.py'),
               'command': tests['positive']['command'], 'test_exit_code': 0,
               'test_log': tests['positive']['log'],
               'test_log_sha256': tests['positive']['log_sha256'],
               'negative_command': tests['negative']['command'],
               'negative_exit_code': 1,
               'negative_expected_error': 'Missing exact original Native beam result',
               'negative_log': tests['negative']['log'],
               'negative_log_sha256': tests['negative']['log_sha256']}
    (ROOT/'native'/f'delivery-{probe}-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('PASS', probe)
