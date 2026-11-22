"""Re-execute the selected synthetic physical and lifecycle CPU fixtures."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = f'work/{HERE.name}/'
OUTPUT = HERE/'current-runtime-physical-fixtures'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE/'current-runtime-reproof-manifest.json').read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        script = 'prove-control-physical.py' if suffix == 'control' else 'prove-selected-physical.py'
        destination = OUTPUT/suffix
        destination.mkdir(parents=True, exist_ok=True)
        proof = {'format': 'c110812-current-runtime-physical-cpu-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
                 'script_sha256': sha(HERE/script), 'fixtures': [],
                 'scope': 'synthetic source-shaped motion/lifecycle only; original Native, pixels, physical and legal acceptance unverified'}
        for kind in KINDS:
            result = destination/(kind+'.json')
            log = destination/(kind+'.log')
            command = [sys.executable, str(HERE/script)]
            if suffix != 'control':
                command += ['--suffix', suffix]
            command += ['--kind', kind, '--output', str(result)]
            with log.open('w') as stream:
                code = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT).returncode
            if code != 0:
                raise RuntimeError(f'{suffix} {kind} physical fixture failed; see {log}')
            row = {'command': f'.venv-cpu/bin/python {PREFIX}{script} '+
                   (f'--suffix {suffix} ' if suffix != 'control' else '')+
                   f'--kind {kind} --output {PREFIX}current-runtime-physical-fixtures/{suffix}/{kind}.json',
                   'exit_code': code, 'log': f'current-runtime-physical-fixtures/{suffix}/{kind}.log',
                   'log_sha256': sha(log), 'result': f'current-runtime-physical-fixtures/{suffix}/{kind}.json',
                   'result_sha256': sha(result)}
            if kind == 'lifecycle':
                row['events'] = json.loads(result.read_text())['events']
                proof['lifecycle'] = row
            else:
                row['kind'] = kind
                proof['fixtures'].append(row)
        (destination/'proof.json').write_text(json.dumps(proof, indent=2)+'\n')
        print(suffix, 'physical and lifecycle CPU fixtures passed', flush=True)


if __name__ == '__main__':
    main()
