"""Run and bind the three exact synthetic physical outcomes and lifecycle proof."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    env = os.environ.copy()
    env['TMPDIR'] = str(ROOT / '.runtime-work')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/nrs497-pipeline')
    result = subprocess.run(command, cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, check=False)
    log.write_text(result.stdout.rstrip() + '\n')
    if result.returncode:
        raise RuntimeError(f'Physical proof failed: {result.stdout[-1000:]}')
    return result.returncode


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        directory = HERE / 'physical' / suffix
        directory.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in KINDS:
            result = directory / (kind + '.json')
            log = directory / (kind + '.log')
            command = [sys.executable, str(HERE / 'prove_physical.py'),
                       '--case', suffix, '--kind', kind, '--output', str(result)]
            exit_code = run(command, log)
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': exit_code, 'log': str(log.relative_to(HERE)),
                             'log_sha256': sha(log),
                             'result': str(result.relative_to(HERE)),
                             'result_sha256': sha(result)})
        lifecycle_result = directory / 'lifecycle.json'
        lifecycle_log = directory / 'lifecycle.log'
        command = [sys.executable, str(HERE / 'prove_physical.py'),
                   '--case', suffix, '--kind', 'lifecycle', '--output', str(lifecycle_result)]
        run(command, lifecycle_log)
        lifecycle = json.loads(lifecycle_result.read_text())
        lifecycle.update({'command': ' '.join(command), 'exit_code': 0,
                          'log': str(lifecycle_log.relative_to(HERE)),
                          'log_sha256': sha(lifecycle_log)})
        receipt_path = directory / 'receipt.json'
        receipt = {'format': 'worker-physical-preparation', 'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures, 'lifecycle': lifecycle,
                   'scope': 'synthetic CPU outcomes only; original Native and legal review pending'}
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': str(receipt_path.relative_to(HERE)),
                                         'sha256': sha(receipt_path)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    (HERE / 'selected-parking-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'physical_receipts': len(manifest['cases'])}))


if __name__ == '__main__':
    main()
