"""Run pinned offline preflight for all eight unselected exception-b bundles."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=HERE/'draft-exception-b-execution-manifest.json'
PYTHON=ROOT/'.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads(MANIFEST.read_text())
    assert manifest['status']=='draft_not_selected' and len(manifest['cases'])==2
    env=dict(os.environ)
    env['LD_LIBRARY_PATH']=str(ROOT/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c10052-exception-b-offline-'))
    receipts=[]
    for entry in manifest['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        for name in ('primary','fallback1','fallback2','fallback3'):
            ref=entry if name=='primary' else next(c for c in entry['candidates'] if c['id']==name)
            output=scratch/(suffix+'-'+name)
            command=[str(PYTHON),str(ROOT/'runtime.py'),'offline',
                '--manifest',str(MANIFEST),'--case',entry['case_id'],
                '--candidate',name,'--output',str(output),'--python',str(PYTHON)]
            result=subprocess.run(command,cwd=ROOT,env=env,text=True,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            log=HERE/'draft-exception-b-exact-cases'/suffix/name/'command.log'
            log.write_text(result.stdout)
            unit=output/'offline.log'
            receipts.append({'case_id':entry['case_id'],'candidate_id':name,
                'exit_code':result.returncode,'construction_sha256':ref['construction_sha256'],
                'command_log':log.relative_to(HERE).as_posix(),
                'command_log_sha256':sha(log),
                'unit_log':unit.relative_to(ROOT).as_posix() if unit.is_file() else None,
                'unit_log_sha256':sha(unit) if unit.is_file() else None,
                'simulation_started':False,'selected':False})
            print(suffix,name,result.returncode,flush=True)
    summary={'format':'c10052-exact-exception-b-offline-v1',
        'manifest_sha256':sha(MANIFEST),'results':receipts,
        'passed':all(x['exit_code']==0 and x['unit_log_sha256'] for x in receipts),
        'original_native_capture_executed':False,'selected':False}
    (HERE/'exception-b-case-offline-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if not summary['passed']:raise SystemExit(1)


if __name__=='__main__':main()
