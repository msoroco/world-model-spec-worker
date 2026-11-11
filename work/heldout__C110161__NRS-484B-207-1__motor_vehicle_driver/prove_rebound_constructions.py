"""Rerun exact offline and source-bound compatibility for all overtaking plans."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
from time import time_ns

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUNTIME=ROOT/'runtime.py'
VALIDATOR=ROOT/'.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(command,log):
    with log.open('w') as stream:
        subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)

def prove():
    updated={}
    for name in ('delivery-construction-manifest.json','variant-construction-manifest.json'):
        path=HERE/name
        manifest=json.loads(path.read_text())
        for entry in manifest['cases']:
            suffix=entry['case_id'].rsplit('__',1)[-1]
            for choice in [entry,*entry['candidates']]:
                candidate=choice.get('id','primary')
                stem=f'delivery-{suffix}' + ('' if candidate=='primary' else '-'+candidate)
                token=str(time_ns())
                offline_out=ROOT/'.runtime-work'/f'c110161-rebound-{suffix}-{candidate}-{token}-offline'
                offline_command=[sys.executable,str(RUNTIME),'offline','--manifest',str(path),
                    '--case',entry['case_id'],'--candidate',candidate,'--output',str(offline_out),
                    '--python',sys.executable]
                offline_log=HERE/(stem+'-offline.log')
                run(offline_command,offline_log)
                choice['offline']={'command':' '.join(offline_command),'exit_code':0,
                    'log':offline_log.name,'log_sha256':sha(offline_log),
                    'construction_sha256':choice['construction_sha256']}
                compat_out=ROOT/'.runtime-work'/f'c110161-rebound-{suffix}-{candidate}-{token}-compat'
                compat_command=[sys.executable,str(RUNTIME),'compatibility','--manifest',str(path),
                    '--case',entry['case_id'],'--candidate',candidate,'--output',str(compat_out),
                    '--library',str(ROOT/'runtime/library'),'--validator',str(VALIDATOR)]
                compat_command_log=HERE/(stem+'-compat-command.log')
                run(compat_command,compat_command_log)
                receipt=HERE/(stem+'-compatibility.json')
                analysis_log=HERE/(stem+'-compat.log')
                negative_log=HERE/(stem+'-negative.log')
                shutil.copy2(compat_out/'compatibility.json',receipt)
                shutil.copy2(compat_out/'compatibility-analysis.log',analysis_log)
                shutil.copy2(compat_out/'negative-analysis.log',negative_log)
                choice['compatibility']={'receipt':receipt.name,'sha256':sha(receipt),
                    'log':analysis_log.name,'negative_log':negative_log.name}
                if candidate=='primary':
                    choice['negative']={'log':negative_log.name}
                print(suffix,candidate,'offline and compatibility passed',flush=True)
            updated[entry['case_id']]=entry
        path.write_text(json.dumps(manifest,indent=2)+'\n')
    execution_path=HERE/'execution-manifest.json'
    execution=json.loads(execution_path.read_text())
    for entry in execution['cases']:
        source=updated[entry['case_id']]
        for key in ('construction_sha256','offline','compatibility','negative'):
            entry[key]=source[key]
        entry['candidates']=source['candidates']
    execution_path.write_text(json.dumps(execution,indent=2)+'\n')
    print('Bound current primary and fallback proofs in execution manifest')

if __name__=='__main__':
    prove()
