"""Bind original-source rejection contracts and source-shaped physical CPU proofs."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    script = HERE / 'delivery_audit.py'
    folder = HERE / 'delivery-proofs'
    folder.mkdir(exist_ok=True)
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        commands = []
        results = []
        for negative in (False, True):
            command = ['.venv-cpu/bin/python', '-B',
                       str(script.relative_to(ROOT)), '--case', case,
                       '--self-test'] + (['--negative'] if negative else [])
            process = subprocess.run(command, cwd=ROOT, capture_output=True,
                                     text=True, env={**os.environ,
                                                     'PYTHONDONTWRITEBYTECODE': '1'})
            log = folder / (suffix + ('-negative.log' if negative else '-positive.log'))
            log.write_text((process.stdout + process.stderr).rstrip() + '\n')
            commands.append(command)
            results.append((process.returncode, log))
        if results[0][0] != 0 or results[1][0] == 0:
            raise ValueError('Delivery self-test failed for ' + case)
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'], 'checks': list(CHECKS),
            'command': ' '.join(commands[0]),
            'negative_command': ' '.join(commands[1]),
            'script': str(script.relative_to(HERE)),
            'script_sha256': sha(script),
            'test_exit_code': results[0][0],
            'negative_exit_code': results[1][0],
            'negative_expected_error': 'Missing original source',
            'test_log': str(results[0][1].relative_to(HERE)),
            'test_log_sha256': sha(results[0][1]),
            'negative_log': str(results[1][1].relative_to(HERE)),
            'negative_log_sha256': sha(results[1][1]),
        }
        physical = HERE / 'physical-proof' / suffix / 'proof.json'
        if not physical.is_file():
            raise ValueError('Physical CPU proof absent: ' + suffix)
        entry['physical_preparation'] = {
            'receipt': str(physical.relative_to(HERE)), 'sha256': sha(physical)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    main()
