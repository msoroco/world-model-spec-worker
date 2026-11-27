"""Run seven controlled-comparison CPU isolation and rejection checks."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
SCRIPT = FOLDER / 'comparison_audit.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    directory = FOLDER / 'comparison-proofs'
    directory.mkdir(exist_ok=True)
    for comparison in plan['comparisons']:
        ident = comparison['comparison_id']
        suffix = ident.rsplit('__', 1)[-1]
        for negative in (False, True):
            label = 'negative' if negative else 'positive'
            cmd = [str(ROOT / '.venv-cpu/bin/python'), '-B', str(SCRIPT),
                   '--comparison', ident, '--self-test']
            if negative:
                cmd.append('--negative')
            log = directory / f'{suffix}-{label}.log'
            with log.open('w') as stream:
                result = subprocess.run(cmd, cwd=ROOT, stdout=stream,
                                        stderr=subprocess.STDOUT)
            if (result.returncode == 0) == negative:
                raise ValueError(f'Comparison {suffix} {label} returned unexpected status')
            if negative and 'comparison fixed source changed' not in log.read_text():
                raise ValueError('Negative comparison did not reject changed road edge')
            comparison.setdefault('cpu_proof', {})[label] = {
                'command': ' '.join(cmd), 'exit_code': result.returncode,
                'log': str(log.relative_to(FOLDER)), 'log_sha256': sha(log)}
        print(suffix, 'controlled comparison tested', flush=True)
    (FOLDER / 'case-plan.json').write_text(json.dumps(plan, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
