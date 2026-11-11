"""Run the current runtime offline launcher against all 16 packaged constructions."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'draft-execution-manifest.json'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest=json.loads(MANIFEST.read_text())
    results=[]
    for entry in manifest['cases']:
        case=entry['case_id'].rsplit('__',1)[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            output=REPO/'.runtime-work'/'update015-c111662-current-offline'/case/candidate
            if output.exists():shutil.rmtree(output)
            output.parent.mkdir(parents=True,exist_ok=True)
            command=[str(REPO/'.venv-cpu/bin/python'),str(REPO/'runtime.py'),'offline',
                     '--manifest',str(MANIFEST),'--case',entry['case_id'],
                     '--candidate',candidate,'--output',str(output),
                     '--python',str(REPO/'.venv-cpu/bin/python')]
            result=subprocess.run(command,cwd=REPO,capture_output=True,text=True)
            log=ROOT/f'update015-current-{case}-{candidate}-offline.log'
            source=output/'offline.log'
            log.write_text(result.stdout+result.stderr+('\n'+source.read_text() if source.is_file() else ''))
            if result.returncode:
                raise ValueError(f'Current offline failed: {case}/{candidate}: {log}')
            construction=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            results.append({'case_id':entry['case_id'],'candidate_id':candidate,
                            'construction_sha256':construction['construction_sha256'],
                            'exit_code':0,'log':log.name,'log_sha256':sha(log)})
    output=ROOT/'update015-current-offline-matrix.json'
    output.write_text(json.dumps({'format':'c111662-current-offline-matrix-v1',
                                  'manifest_sha256':sha(MANIFEST),'results':results},indent=2)+'\n')
    print(json.dumps({'current_offline_passed':len(results)}))


if __name__=='__main__':main()
