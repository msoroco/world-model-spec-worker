"""Run the eight exact selected saved-source compatibility checks and bind receipts."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
VALIDATOR = REPO / '.runtime-work/c102372-active-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ)
    env['TMPDIR'] = str(REPO / '.runtime-work')
    env['MPLCONFIGDIR'] = str(REPO / '.runtime-work/mpl')
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c255451-compat-runtime')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        output = REPO / '.runtime-work' / ('c255451-compat2-condition_b' if condition == 'condition_b' else 'c255451-compat3-' + condition)
        command = [sys.executable, '-B', 'runtime.py', 'compatibility', '--manifest',
                   str(MANIFEST.relative_to(REPO)), '--case', entry['case_id'],
                   '--output', str(output.relative_to(REPO)), '--library', 'runtime/library',
                   '--validator', str(VALIDATOR.relative_to(REPO))]
        if not (output / 'compatibility.json').is_file():
            if output.exists():
                raise ValueError('Incomplete compatibility output; choose fresh name: ' + str(output))
            print('compatibility ' + condition, flush=True)
            proc = subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                                  text=True, timeout=900)
            if proc.returncode:
                raise RuntimeError(condition + ' compatibility failed: ' + (proc.stderr or proc.stdout)[-4000:])
        proof = json.loads((output / 'compatibility.json').read_text())
        if proof.get('passed') is not True or proof.get('case_id') != entry['case_id'] or proof.get('construction_sha256') != entry['construction_sha256']:
            raise ValueError('Stale exact selected compatibility: ' + condition)
        dest = HERE / 'selected' / condition
        for source, target in (('compatibility.json', 'compatibility.json'),
                               ('compatibility-analysis.log', 'compatibility-analysis.log'),
                               ('negative-analysis.log', 'negative-analysis.log')):
            shutil.copyfile(output / source, dest / target)
        entry['compatibility'] = {
            'command': '.venv-cpu/bin/python -B runtime.py compatibility --manifest '
                       + str(MANIFEST.relative_to(REPO)) + ' --case ' + entry['case_id']
                       + ' --output ' + str(output.relative_to(REPO))
                       + ' --library runtime/library --validator ' + str(VALIDATOR.relative_to(REPO)),
            'receipt': str((dest / 'compatibility.json').relative_to(ROOT)),
            'sha256': sha(dest / 'compatibility.json'),
            'log': str((dest / 'compatibility-analysis.log').relative_to(ROOT)),
        }
        entry['negative'] = {'log': str((dest / 'negative-analysis.log').relative_to(ROOT))}
        temporary = REPO / '.runtime-work/c255451-manifest-next.json'
        temporary.write_text(json.dumps(manifest, indent=2) + '\n')
        temporary.replace(MANIFEST)
        print('bound ' + condition, flush=True)


if __name__ == '__main__':
    bind()
