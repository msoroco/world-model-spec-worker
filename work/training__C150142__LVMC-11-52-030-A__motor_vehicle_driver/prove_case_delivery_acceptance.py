"""Run positive and missing-original-source CPU checks for every exact case."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRIPT = HERE / 'case_delivery_acceptance.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    cases = [entry['case_id'] for entry in manifest['cases']]
    if len(cases) != len(set(cases)) or len(cases) != 30:
        raise ValueError('Exact case selection incomplete')
    folder = HERE / 'case-delivery-proofs'
    folder.mkdir(exist_ok=True)
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['TMPDIR'] = str(REPO / '.runtime-work')
    rows = []
    for case in cases:
        slug = case.rsplit('__', 1)[1]
        commands = []
        for negative in (False, True):
            args = [sys.executable, str(SCRIPT), '--case', case]
            if negative:
                args.append('--missing-source')
            result = subprocess.run(args, cwd=REPO, env=env,
                                    capture_output=True, text=True)
            log = folder / (slug + ('-negative' if negative else '-positive') + '.log')
            log.write_text((result.stdout + result.stderr).rstrip() + '\n')
            if negative:
                if result.returncode == 0 or 'Missing independent original Native and physical acceptance source' not in log.read_text():
                    raise ValueError('Missing original source negative did not reject: ' + case)
            elif result.returncode != 0 or json.loads(result.stdout)['case_id'] != case:
                raise ValueError('Exact case delivery CPU test failed: ' + case)
            commands.append({'command': ' '.join(['PYTHONDONTWRITEBYTECODE=1',
                       'TMPDIR=$PWD/.runtime-work', '.venv-cpu/bin/python',
                       str(SCRIPT.relative_to(REPO)), '--case', case] +
                       (['--missing-source'] if negative else [])),
                       'exit_code': result.returncode,
                       'log': str(log.relative_to(HERE)), 'log_sha256': sha(log)})
        rows.append({'case_id': case, 'positive': commands[0],
                     'negative': commands[1]})
    receipt = {'format': 'c150142-exact-case-delivery-cpu-index-v1',
               'passed': True, 'script': str(SCRIPT.relative_to(HERE)),
               'script_sha256': sha(SCRIPT), 'cases': rows,
               'synthetic_only': True, 'original_native_observed': False,
               'physical_acceptance_claimed': False}
    path = HERE / 'current-exact-case-delivery-cpu-index.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    return {'cases': len(rows), 'index_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
