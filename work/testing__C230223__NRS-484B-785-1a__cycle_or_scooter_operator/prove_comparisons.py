"""CPU source-bound positive and negative comparison proofs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from package_spec import AID

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work'/'c230223_7851a_owner'
PYTHON=ROOT/'.venv-cpu/bin/python'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

def logged(command,log,env):
    result=subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,text=True)
    content='\n'.join(line.rstrip() for line in result.stdout.rstrip().splitlines())
    log.write_text(content+'\n' if content else '')
    return result

def main(tag):
    plan=json.loads((HERE/'case-plan.json').read_text())
    manifest_path=HERE/'execution-manifest.draft.json'
    manifest=json.loads(manifest_path.read_text())
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',
             SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH/'output'),
             TMPDIR=str(SCRATCH/'tmp'))
    receipts=[]
    for comparison in plan['comparisons']:
        coid=comparison['comparison_id']
        index=SCRATCH/tag/(coid+'-source-index.json')
        write(index,{'format':'scooter-785-comparison-sources',
                     'assignment_id':AID,
                     'cases':{cid:str(SCRATCH/'all-v1'/'compatibility'/
                                      cid.removeprefix(AID+'__')/'primary')
                              for cid in comparison['case_ids']}})
        base=[str(PYTHON),str(HERE/'comparison_audit.py'),
              '--comparison-id',coid,'--source-index',str(index)]
        positive_log=HERE/('proof-comparison-'+coid+'-positive.log')
        negative_log=HERE/('proof-comparison-'+coid+'-negative.log')
        positive=logged(base,positive_log,env)
        negative=logged(base+['--diagnostic-fault','fixed'],negative_log,env)
        error=('Fixed condition changed: ordinance_context.kind'
               if coid=='scooter_qualification'
               else 'Fixed condition changed: scooter_qualification.qualifies')
        if (positive.returncode or json.loads(positive.stdout).get('passed') is not True
                or negative.returncode==0 or error not in negative.stdout):
            raise ValueError('comparison proof failed: '+coid+'\n'+positive.stdout+'\n'+negative.stdout)
        receipts.append({'comparison_id':coid,'case_ids':comparison['case_ids'],
                         'positive_command':' '.join(base),
                         'negative_command':' '.join(base+['--diagnostic-fault','fixed']),
                         'test_exit_code':0,'negative_exit_code':negative.returncode,
                         'negative_expected_error':error,
                         'script':'comparison_audit.py','script_sha256':sha(HERE/'comparison_audit.py'),
                         'test_log':positive_log.name,'test_log_sha256':sha(positive_log),
                         'negative_log':negative_log.name,'negative_log_sha256':sha(negative_log),
                         'scope':'CPU source-bound diagnostic comparison only; original CARLA pixels and legal verdict require local review'})
        print('comparison positive/negative passed',coid,flush=True)
    manifest['comparison_audits']=receipts
    write(manifest_path,manifest)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--tag',required=True)
    args=parser.parse_args()
    main(args.tag)
