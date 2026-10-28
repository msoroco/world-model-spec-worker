"""Run every exact offline case and freeze hashed partition 04 result logs."""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ROOT=pathlib.Path(__file__).resolve().parents[2]
PARTITION=json.loads((ROOT/'partitions/demo-test-04.json').read_text())['assignment_ids']
sys.path.insert(0,str(ROOT/'runtime/main-pipeline-v1/scenario_pipeline'))
from worker_exchange.execution_manifest import validate


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def main():
    for aid in PARTITION:
        folder=ROOT/'work'/aid
        manifest=validate(ROOT,aid)
        tests=[]
        for index,entry in enumerate(manifest['cases']):
            output=ROOT/'.runtime-work'/('part04-final02-'+aid.split('__')[1]+'-'+str(index))
            command=[sys.executable,str(ROOT/'runtime.py'),'offline','--manifest',str(folder/'execution-manifest.json'),
                '--case',entry['case_id'],'--output',str(output)]
            completed=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
            if completed.returncode:
                print(completed.stdout,completed.stderr,file=sys.stderr)
                raise RuntimeError('Offline case failed: '+entry['case_id'])
            source=output/'offline.log'
            log=folder/'tests'/('offline-'+str(index)+'.log')
            shutil.copyfile(source,log)
            tests.append({'command':' '.join(command),'exit_code':completed.returncode,
                          'log':str(log.relative_to(folder)),'sha256':sha(log)})
            print(entry['case_id'],'passed')
        smoke=subprocess.run([sys.executable,str(folder/'analyze.py'),'--help'],cwd=folder,
                             text=True,capture_output=True)
        if smoke.returncode:raise RuntimeError('Analyzer import smoke failed: '+aid+' '+smoke.stderr)
        smoke_log=folder/'tests/analyze-help.log';smoke_log.write_text(smoke.stdout+smoke.stderr)
        tests.append({'command':sys.executable+' '+str(folder/'analyze.py')+' --help',
                      'exit_code':0,'log':'tests/analyze-help.log','sha256':sha(smoke_log)})
        batch=json.loads((ROOT/'batch.json').read_text())
        result={'assignment_id':aid,'input_sha256':batch['assignments'][aid]['input_sha256'],
                'status':'ready','readiness_kind':'capability','applied_update':4,'tests':tests,
                'physical_acceptance':False}
        write(folder/'result.json',result)


if __name__=='__main__':main()
