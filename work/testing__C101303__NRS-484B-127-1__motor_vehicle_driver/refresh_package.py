"""Rerun exact pinned offline and compatibility proofs after bundled code changes."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = REPO/'.venv-cpu/bin/python'
MANIFEST = ROOT/'execution-manifest.json'
VALIDATOR = REPO/'.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, output):
    if output.exists():
        shutil.rmtree(output)
    result = subprocess.run(command, cwd=REPO, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(' '.join(command)+'\n'+result.stdout[-2000:])


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(ROOT.name+'__')
        for candidate, holder in [('primary',entry),
                                  ('fallback1',entry['candidates'][0])]:
            output = REPO/'.runtime-work'/('c101303-offline6-'+suffix+'-'+candidate)
            command = [str(PYTHON), str(REPO/'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', candidate, '--output', str(output),
                       '--python', str(PYTHON)]
            run(command, output)
            log = ROOT/('proof-offline-'+suffix+'-'+candidate+'.log')
            shutil.copyfile(output/'offline.log', log)
            holder['offline'] = {'command': ' '.join(command), 'exit_code': 0,
                'construction_sha256': holder['construction_sha256'],
                'log': log.name, 'log_sha256': sha(log)}
            MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
            output = REPO/'.runtime-work'/('c101303-compat4-'+suffix+'-'+candidate)
            command = [str(PYTHON), str(REPO/'runtime.py'), 'compatibility',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', candidate, '--output', str(output),
                       '--library', str(REPO/'runtime/library'),
                       '--validator', str(VALIDATOR)]
            run(command, output)
            files = {}
            for key, source, ending in (
                ('receipt','compatibility.json','-receipt.json'),
                ('log','compatibility-analysis.log','-analysis.log'),
                ('negative_log','negative-analysis.log','-negative.log')):
                target = ROOT/('compat-'+suffix+'-'+candidate+ending)
                shutil.copyfile(output/source, target)
                files[key] = target.name
                if key == 'receipt':
                    files['sha256'] = sha(target)
            files['command'] = ' '.join(command)
            holder['compatibility'] = files
            if candidate == 'primary':
                entry['negative'] = {'log': files['negative_log']}
            MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    count = 2*len(manifest['cases'])
    print(f'{count} exact offline and {count} positive/missing-source compatibility proofs refreshed.')


if __name__ == '__main__':
    main()
