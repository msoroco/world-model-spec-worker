"""Refresh exact C109755 bundles and CPU receipts after analyzer changes."""
import hashlib
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'execution-manifest.json'
OUTPUT=REPO/'.runtime-work/c109755-traffic-sweep-proof'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')


def run(command,output,log,env):
    args=shlex.split(command)
    args[args.index('--output')+1]=str(output)
    if output.exists():shutil.rmtree(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    completed=subprocess.run(args,cwd=REPO,env=env,text=True,
                             stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    log.write_text(completed.stdout)
    if completed.returncode:
        raise RuntimeError(f'{log.name} failed: {completed.stdout[-1500:]}')
    return ' '.join(shlex.quote(arg) for arg in args)


def main():
    env=dict(os.environ,SCENARIO_PIPELINE_OUTPUT_ROOT=str(OUTPUT),
             PYTHONDONTWRITEBYTECODE='1',
             PYTHONPATH=str(REPO/'runtime/scenario_pipeline')+':'+str(REPO/'runtime/python'))
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        label='unsignaled' if '__unsignaled_' in entry['case_id'] else 'signaled'
        for candidate in (entry,*entry['candidates']):
            name=candidate.get('id','primary')
            path=ROOT/candidate['construction']
            construction=json.loads(path.read_text())
            included=('analysis.py','native_capture.py','delivery_audit.py',
                      'delivery_probe.py','traffic_sweep.py','traffic_sweep_audit.py',
                      'tests/test_construction.py','tests/test_native_capture.py',
                      'tests/test_traffic_sweep_audit.py')
            existing={file['path'] for file in construction['files']}
            for name in ('traffic_sweep.py','traffic_sweep_audit.py',
                         'tests/test_traffic_sweep_audit.py'):
                if name not in existing:
                    construction['files'].append({'path':name,'content':''})
            for file in construction['files']:
                if file['path'] in included:
                    file['content']=(ROOT/file['path']).read_text()
            write(path,construction)
            candidate['construction_sha256']=sha(path)
            candidate['offline']['construction_sha256']=sha(path)
        write(MANIFEST,manifest)
        for candidate in (entry,*entry['candidates']):
            name=candidate.get('id','primary')
            base=OUTPUT/label/name
            offline=candidate['offline']
            log=ROOT/f'proof-{label}-{name}-window.log'
            offline['command']=run(offline['command'],base/'offline',log,env)
            offline['log']=log.name;offline['log_sha256']=sha(log);offline['exit_code']=0
            write(MANIFEST,manifest)
            compat=candidate['compatibility']
            command_log=ROOT/f'compat-{label}-{name}-window-receipt.json'
            compat['command']=run(compat['command'],base/'compat',command_log,env)
            shutil.copyfile(base/'compat/compatibility-analysis.log',ROOT/f'compat-{label}-{name}-window-analysis.log')
            shutil.copyfile(base/'compat/negative-analysis.log',ROOT/f'compat-{label}-{name}-window-negative.log')
            compat.update({'receipt':command_log.name,'sha256':sha(command_log),
                           'command_log':command_log.name,'command_log_sha256':sha(command_log),
                           'log':f'compat-{label}-{name}-window-analysis.log',
                           'negative_log':f'compat-{label}-{name}-window-negative.log',
                           'exit_code':0})
            if name=='primary':
                candidate['negative']={'log':compat['negative_log'],
                                       'sha256':sha(ROOT/compat['negative_log'])}
            write(MANIFEST,manifest)
        physical=OUTPUT/label/'physical'
        if physical.exists():shutil.rmtree(physical)
        command=[str(REPO/'.venv-cpu/bin/python'),str(ROOT/'physical_probe.py'),
                 '--case',entry['case_id'],'--output',str(physical)]
        completed=subprocess.run(command,cwd=REPO,env=env,text=True,
                                 stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        log=ROOT/f'physical-{label}-window.log';log.write_text(completed.stdout)
        if completed.returncode:raise RuntimeError(log.name+': '+completed.stdout[-1000:])
        receipt=ROOT/f'physical-{label}-proof.json'
        proof=json.loads(receipt.read_text());proof['construction_sha256']=entry['construction_sha256']
        for fixture in proof['fixtures']:
            fixture.update({'command':' '.join(command),'log':log.name,
                            'log_sha256':sha(log),
                            'result_sha256':sha(ROOT/fixture['result'])})
        proof['lifecycle'].update({'log':log.name,'log_sha256':sha(log)})
        write(receipt,proof)
        entry['physical_preparation']={'receipt':receipt.name,'sha256':sha(receipt)}
        write(MANIFEST,manifest)
    print('refreshed four exact offline and compatibility bundles plus physical fixtures')


if __name__=='__main__':main()
