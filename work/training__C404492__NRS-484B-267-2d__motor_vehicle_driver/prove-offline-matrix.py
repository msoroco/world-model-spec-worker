"""Run every exact primary and fallback construction through current CPU offline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    scratch = args.scratch.resolve()
    if root / '.runtime-work' not in scratch.parents:
        raise ValueError('Scratch must be under .runtime-work')
    scratch.mkdir(parents=True, exist_ok=True)
    manifest = here / 'draft-emergency-manifest.json'
    entries = json.loads(manifest.read_text())['cases']
    rows = []
    for entry in entries:
        case = entry['case_id']
        for candidate in ('primary', 'fallback1', 'fallback2'):
            with tempfile.TemporaryDirectory(prefix='offline-', dir=scratch) as temp:
                output = Path(temp) / 'attempt'
                command = [str(root / '.venv-cpu/bin/python'), str(root / 'runtime.py'),
                           'offline', '--manifest', str(manifest), '--case', case,
                           '--candidate', candidate, '--output', str(output),
                           '--python', str(root / '.venv-cpu/bin/python')]
                env = os.environ.copy()
                env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(scratch / 'runtime-output')
                env['TMPDIR'] = str(scratch)
                env['PYTHONDONTWRITEBYTECODE'] = '1'
                run = subprocess.run(command, capture_output=True, text=True, env=env)
                if run.returncode:
                    raise ValueError('Offline candidate failed: ' + case + ' ' + candidate + '\n' + run.stderr[-1000:])
                result = json.loads(run.stdout)
                if result.get('offline_passed') is not True or result.get('simulation_started') is not False:
                    raise ValueError('Offline result did not prove CPU construction')
                construction = (entry if candidate == 'primary' else
                                next(x for x in entry['candidates'] if x['id'] == candidate))
                path = here / construction['construction']
                if sha(path) != construction['construction_sha256']:
                    raise ValueError('Construction hash differs')
                name = case.rsplit('__', 1)[-1] + '-' + candidate
                retained_log = here / 'current-offline' / (name + '.log')
                retained_log.parent.mkdir(parents=True, exist_ok=True)
                data = (output / 'offline.log').read_bytes()
                if (not data.endswith(b'\n') or data.endswith(b'\n\n')
                        or any(line != line.rstrip() for line in data.splitlines())):
                    raise ValueError('Offline log whitespace differs: ' + name)
                retained_log.write_bytes(data)
                rows.append({'case_id': case, 'candidate_id': candidate,
                             'construction_sha256': sha(path),
                             'offline_log_sha256': sha(retained_log),
                             'offline_passed': True, 'simulation_started': False})
    print(json.dumps({'format': 'c404492-current-candidate-offline-matrix',
                      'manifest_sha256': sha(manifest), 'candidates': rows,
                      'status': 'partial_selected_cpu_draft'}, indent=2))


if __name__ == '__main__':
    main()
