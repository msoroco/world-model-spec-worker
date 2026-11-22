"""Refresh the two exact draft inline bundles and CPU offline receipts."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT/'execution-manifest.json'
PYTHON = REPO/'.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(ROOT.name+'__')
        path = ROOT/entry['construction']
        construction = json.loads(path.read_text())
        included = {item['path'] for item in construction['files']}
        for name in ('native_samples.py', 'native_capture.py',
                     'tests/test_native_samples.py', 'tests/test_native_capture.py'):
            if name not in included:
                construction['files'].append({'path': name, 'content': (ROOT/name).read_text()})
        for item in construction['files']:
            name = item['path']
            if name in ('runner.py','analysis.py','native_samples.py','native_capture.py',
                        'tests/test_construction.py','tests/test_native_samples.py',
                        'tests/test_native_capture.py'):
                item['content'] = (ROOT/name).read_text()
        path.write_text(json.dumps(construction,indent=2)+'\n')
        entry['construction_sha256'] = sha(path)
        entry.pop('offline',None)
        output = REPO/'.runtime-work'/('c10808-offline-refresh-'+suffix)
        if output.exists():
            shutil.rmtree(output)
        command = [str(PYTHON),str(REPO/'runtime.py'),'offline',
                   '--manifest',str(MANIFEST),'--case',entry['case_id'],
                   '--output',str(output),'--python',str(PYTHON)]
        MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
        result = subprocess.run(command,cwd=REPO,text=True,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(suffix+': '+result.stdout[-1500:])
        log = ROOT/('proof-'+suffix+'.log')
        shutil.copyfile(output/'offline.log',log)
        entry['offline']={'command':' '.join(command),'exit_code':0,
                          'construction_sha256':entry['construction_sha256'],
                          'log':log.name,'log_sha256':sha(log)}
        MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    print('Two exact draft offline bundles refreshed.')


if __name__=='__main__':
    main()
