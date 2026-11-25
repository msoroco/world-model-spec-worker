"""Execute and source-bind three physical outcomes plus Native ownership order."""
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
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    env = os.environ.copy()
    env['TMPDIR'] = str(ROOT / '.runtime-work')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c150916-pipeline')
    done = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                          text=True, check=False)
    log.write_text((done.stdout + done.stderr).rstrip() + '\n')
    if done.returncode:
        raise RuntimeError('Physical source proof failed: ' + (done.stdout + done.stderr)[-1000:])
    return done.returncode


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        direction = entry['case_id'].rsplit('__', 1)[1]
        folder = HERE / 'physical' / direction
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in KINDS:
            result = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, str(HERE / 'prove_selected_physical.py'),
                       '--case', direction, '--kind', kind, '--output', str(result)]
            exit_code = run(command, log)
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': exit_code, 'log': str(log.relative_to(HERE)),
                             'log_sha256': sha(log), 'result': str(result.relative_to(HERE)),
                             'result_sha256': sha(result)})
        result = folder / 'lifecycle.json'
        log = folder / 'lifecycle.log'
        command = [sys.executable, str(HERE / 'prove_selected_physical.py'),
                   '--case', direction, '--kind', 'lifecycle', '--output', str(result)]
        run(command, log)
        lifecycle = json.loads(result.read_text())
        lifecycle.update({'command': ' '.join(command), 'exit_code': 0,
                          'log': str(log.relative_to(HERE)),
                          'log_sha256': sha(log)})
        receipt = folder / 'receipt.json'
        receipt.write_text(json.dumps({'format': 'worker-physical-preparation',
                                       'case_id': entry['case_id'],
                                       'construction_sha256': entry['construction_sha256'],
                                       'fixtures': fixtures, 'lifecycle': lifecycle,
                                       'scope': 'Synthetic CPU outcomes only; original Native sign and designation review pending'},
                                      indent=2, allow_nan=False) + '\n')
        entry['physical_preparation'] = {'receipt': str(receipt.relative_to(HERE)),
                                         'sha256': sha(receipt)}
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'physical_receipts': len(manifest['cases']),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
