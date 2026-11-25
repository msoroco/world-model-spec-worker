"""Bind exact synthetic bus completion and owner-lifecycle CPU fixtures."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    selected = json.loads((HERE / 'selected-offline-manifest.json').read_text())
    for entry in selected['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            output = folder / (kind + '.json')
            command = f'.venv-cpu/bin/python work/{AID}/prove_selected_physical.py --case {suffix} --kind {kind} --output work/{AID}/physical-proof/{suffix}/{kind}.json'
            result = subprocess.run([sys.executable,
                str(HERE / 'prove_selected_physical.py'), '--case', suffix,
                '--kind', kind, '--output', str(output)], cwd=REPO,
                capture_output=True, text=True)
            log = folder / (kind + '.log')
            log.write_text((result.stdout + result.stderr).strip() + '\n')
            if result.returncode:
                raise RuntimeError(log.read_text())
            fixtures.append({'kind': kind, 'command': command, 'exit_code': 0,
                'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)})
        result = subprocess.run([sys.executable,
            str(HERE / 'prove_selected_physical.py'), '--case', suffix,
            '--kind', 'lifecycle'], cwd=REPO, capture_output=True, text=True)
        log = folder / 'lifecycle.log'
        log.write_text((result.stdout + result.stderr).strip() + '\n')
        if result.returncode:
            raise RuntimeError(log.read_text())
        lifecycle = json.loads(result.stdout)
        lifecycle.update(exit_code=0, log=str(log.relative_to(HERE)),
                         log_sha256=sha(log))
        proof = {'format': 'worker-physical-preparation',
            'case_id': entry['case_id'],
            'construction_sha256': entry['construction_sha256'],
            'fixtures': fixtures, 'lifecycle': lifecycle,
            'scope': 'Synthetic CPU mechanics only; original bus loading, wheel, pixel and traffic review pending'}
        path = folder / 'proof.json'
        path.write_text(json.dumps(proof, indent=2) + '\n')
        print(json.dumps({'case': entry['case_id'], 'proof_sha256': sha(path)}))


if __name__ == '__main__':
    main()
