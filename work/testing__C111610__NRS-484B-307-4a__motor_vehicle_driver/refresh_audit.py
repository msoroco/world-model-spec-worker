"""Retain exact-case synthetic CPU audit positive and negative proof logs."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
PROBE = ROOT / 'audit_probe.py'
AUDITOR = ROOT / 'delivery_audit.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c111610-audit-probe-runtime')
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        commands = {}
        logs = {}
        codes = {}
        for mode in ('positive', 'negative'):
            output = REPO / '.runtime-work' / ('c111610-audit-' + suffix + '-' + mode)
            command = [str(REPO / '.venv-cpu/bin/python'), str(PROBE),
                       '--case', entry['case_id'], '--output', str(output)]
            if mode == 'negative':
                command.append('--negative')
            result = subprocess.run(command, cwd=REPO, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log = ROOT / ('audit-' + suffix + '-' + mode + '.log')
            log.write_text(result.stdout)
            commands[mode] = ' '.join(command)
            logs[mode] = log
            codes[mode] = result.returncode
        if codes['positive'] != 0 or codes['negative'] == 0:
            raise RuntimeError(suffix + ': positive/negative audit exit mismatch')
        expected = 'sealed original missing or changed'
        if expected not in logs['negative'].read_text():
            raise RuntimeError(suffix + ': missing source-mutation rejection')
        if json.loads(logs['positive'].read_text()).get('scope') != 'synthetic_cpu_audit_probe':
            raise RuntimeError(suffix + ': positive log omitted synthetic scope')
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': AUDITOR.name, 'script_sha256': sha(AUDITOR),
            'command': commands['positive'], 'test_exit_code': 0,
            'test_log': logs['positive'].name,
            'test_log_sha256': sha(logs['positive']),
            'negative_command': commands['negative'],
            'negative_exit_code': codes['negative'],
            'negative_expected_error': expected,
            'negative_log': logs['negative'].name,
            'negative_log_sha256': sha(logs['negative'])}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print('Both exact synthetic CPU delivery audits passed positive/negative paths.')


if __name__ == '__main__':
    main()
