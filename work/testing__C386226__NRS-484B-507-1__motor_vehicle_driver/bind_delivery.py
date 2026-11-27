"""Bind independent freight original-source audit commands and CPU rejection proofs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c386226-5071-delivery-negative'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    audit = HERE / 'delivery_audit.py'
    positive_log = HERE / 'cpu-focused-freight.log'
    if 'OK' not in positive_log.read_text():
        raise ValueError('focused audit tests did not pass')
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(HERE.name + '__')
        missing = SCRATCH / ('missing-original-' + suffix)
        output = SCRATCH / ('rejected-' + suffix + '.json')
        command = [sys.executable, str(audit), 'case', '--attempt', str(missing),
                   '--case', case, '--output', str(output)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        content = (result.stdout + result.stderr).rstrip()
        log = HERE / ('proof-original-negative-' + suffix + '.log')
        log.write_text(content + '\n' if content else '')
        if result.returncode == 0 or 'original attempt missing' not in content:
            raise ValueError('missing original source was not rejected: ' + suffix)
        prefix = '.venv-cpu/bin/python work/' + HERE.name + '/delivery_audit.py case --attempt '
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'command': prefix + '$ORIGINAL_ATTEMPT --case ' + case + ' --output $AUDIT_OUTPUT',
            'negative_command': prefix + str(missing) + ' --case ' + case + ' --output ' + str(output),
            'script': 'delivery_audit.py', 'script_sha256': sha(audit),
            'test_exit_code': 0, 'test_log': positive_log.name,
            'test_log_sha256': sha(positive_log),
            'negative_exit_code': result.returncode,
            'negative_expected_error': 'original attempt missing',
            'negative_log': log.name, 'negative_log_sha256': sha(log),
            'scope': 'CPU source-audit implementation tests; original capture and pixel review pending',
        }
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
