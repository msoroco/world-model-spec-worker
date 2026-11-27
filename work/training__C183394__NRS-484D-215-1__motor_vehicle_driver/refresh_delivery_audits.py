"""Refresh independent audit self-tests after source-specific trigger guards."""
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for entry in manifest['cases']:
    case = entry['case_id']
    suffix = case.rsplit('__', 1)[-1]
    checks = {}
    for kind in ('positive', 'negative'):
        command = [str(REPO / '.venv-cpu/bin/python'), '-B', str(ROOT / 'delivery_audit.py'),
                   '--case', case, '--self-test']
        if kind == 'negative':
            command.append('--negative')
        result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        log = ROOT / 'native' / f'delivery-{suffix}-{kind}.log'
        log.write_text(result.stdout + result.stderr)
        if result.returncode != (0 if kind == 'positive' else 1):
            raise RuntimeError(f'{suffix} {kind}: {(result.stdout+result.stderr)[-1000:]}')
        if kind == 'negative' and 'Missing exact original Native beam result' not in log.read_text():
            raise ValueError('Negative auditor did not reject missing Native source')
        checks[kind] = {'command': ' '.join(command), 'exit_code': result.returncode,
                        'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log)}
    receipt = {'case_id': case, 'sets': ['full-train'],
               'checks': ['native_source', 'all_participants', 'time_join',
                          'full_video_decode', 'actual_pixels', 'physical_completion'],
               'script': 'delivery_audit.py', 'script_sha256': sha(ROOT / 'delivery_audit.py'),
               'command': checks['positive']['command'], 'test_exit_code': 0,
               'test_log': checks['positive']['log'],
               'test_log_sha256': checks['positive']['log_sha256'],
               'negative_command': checks['negative']['command'],
               'negative_exit_code': 1,
               'negative_expected_error': 'Missing exact original Native beam result',
               'negative_log': checks['negative']['log'],
               'negative_log_sha256': checks['negative']['log_sha256']}
    path = ROOT / 'native' / f'delivery-{suffix}-receipt.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    entry['delivery_acceptance'] = receipt
    print('AUDIT', suffix, flush=True)
MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
