"""Reprove all exact inline bundles after construction changes."""
import hashlib,json,os,subprocess
from pathlib import Path
OWN=Path(__file__).resolve().parent
REPO=OWN.parents[1]
MANIFEST=OWN/'execution-manifest.json'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

if __name__=='__main__':
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case=entry['case_id'];short=case.removeprefix(manifest['assignment_id']+'__')
        output=REPO/('.runtime-work/c10307-offline-native-v6-'+short)
        command=[str(REPO/'.venv-cpu/bin/python'),str(REPO/'runtime.py'),'offline',
                 '--manifest',str(MANIFEST),'--case',case,'--output',str(output),
                 '--python',str(REPO/'.venv-cpu/bin/python')]
        log=OWN/('cpu-offline-'+short+'.log')
        with log.open('w') as stream:
            process=subprocess.run(command,cwd=REPO,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),
                                   stdout=stream,stderr=subprocess.STDOUT,timeout=300)
        entry['offline']={'command':' '.join(command),'exit_code':process.returncode,
                          'construction_sha256':entry['construction_sha256'],
                          'log':log.name,'log_sha256':sha(log)}
        print(short,process.returncode,sha(log),flush=True)
    MANIFEST.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
