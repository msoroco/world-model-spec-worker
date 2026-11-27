"""Run all exact offline, compatibility and saved-only CPU proofs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work'/'c230223_7851a_owner'
MANIFEST=HERE/'execution-manifest.draft.json'
PYTHON=ROOT/'.venv-cpu/bin/python'
RUNTIME=ROOT/'runtime.py'
LIBRARY=ROOT/'runtime/library'
VALIDATOR=ROOT/'.runtime-work/c150911-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def log_text(path,text):
    cleaned='\n'.join(line.rstrip() for line in text.rstrip().splitlines())
    path.write_text(cleaned+'\n' if cleaned else '')
    if path.stat().st_size>2*1024*1024:
        raise ValueError('CPU proof log exceeds 2 MiB: '+str(path))


def run(command,log,env):
    result=subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,text=True)
    log_text(log,result.stdout)
    if result.returncode:
        raise ValueError('CPU proof failed: '+str(log)+'\n'+result.stdout[-2000:])
    return result


def main(tag):
    env=dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT']=str(SCRATCH/'output')
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['TMPDIR']=str(SCRATCH/'tmp')
    env['MPLCONFIGDIR']=str(SCRATCH/'mpl')
    for name in ('output','tmp','mpl'):
        (SCRATCH/name).mkdir(parents=True,exist_ok=True)
    manifest=json.loads(MANIFEST.read_text())
    results={}
    for entry in manifest['cases']:
        cid=entry['case_id']
        slug=cid.removeprefix(HERE.name+'__')
        results[slug]={}
        for candidate in ('primary','fallback1'):
            offline=SCRATCH/tag/'offline'/slug/candidate
            offline.parent.mkdir(parents=True,exist_ok=True)
            cmd=[str(PYTHON),str(RUNTIME),'offline','--manifest',str(MANIFEST),
                 '--case',cid,'--candidate',candidate,'--output',str(offline),
                 '--python',str(PYTHON)]
            run(cmd,HERE/f'proof-offline-{slug}-{candidate}-command.log',env)
            saved_log=HERE/f'proof-offline-{slug}-{candidate}.log'
            log_text(saved_log,(offline/'offline.log').read_text())
            offline_proof={'command':' '.join(cmd),'exit_code':0,
                           'log':saved_log.name,'log_sha256':sha(saved_log),
                           'construction_sha256':entry['construction_sha256'] if candidate=='primary' else entry['candidates'][0]['construction_sha256']}
            compatibility=SCRATCH/tag/'compatibility'/slug/candidate
            compatibility.parent.mkdir(parents=True,exist_ok=True)
            cmd=[str(PYTHON),str(RUNTIME),'compatibility','--manifest',str(MANIFEST),
                 '--case',cid,'--candidate',candidate,'--output',str(compatibility),
                 '--library',str(LIBRARY),'--validator',str(VALIDATOR)]
            run(cmd,HERE/f'proof-compat-{slug}-{candidate}-command.log',env)
            analysis_log=HERE/f'proof-compat-{slug}-{candidate}-analysis.log'
            negative_log=HERE/f'proof-compat-{slug}-{candidate}-negative.log'
            receipt=HERE/f'proof-compat-{slug}-{candidate}-receipt.json'
            log_text(analysis_log,(compatibility/'compatibility-analysis.log').read_text())
            log_text(negative_log,(compatibility/'negative-analysis.log').read_text())
            shutil.copyfile(compatibility/'compatibility.json',receipt)
            proof={'receipt':receipt.name,'sha256':sha(receipt),
                   'log':analysis_log.name,'negative_log':negative_log.name}
            results[slug][candidate]={'offline':offline_proof,'compatibility':proof,
                                      'attempt':str(compatibility)}
            print('passed',slug,candidate,'offline and compatibility',flush=True)
        attempt=Path(results[slug]['primary']['attempt'])
        output=SCRATCH/tag/'saved'/slug
        output.parent.mkdir(parents=True,exist_ok=True)
        cmd=[str(PYTHON),str(RUNTIME),'process-saved','--manifest',str(MANIFEST),
             '--case',cid,'--attempt',str(attempt),'--output',str(output),
             '--library',str(LIBRARY),'--validator',str(VALIDATOR)]
        saved_log=HERE/f'proof-saved-{slug}.log'
        result=run(cmd,saved_log,env)
        report=json.loads(result.stdout)
        if not (report.get('passed') is True and report.get('recorded_only') is True and
                report.get('originals_preserved') is True):
            raise ValueError('saved-only source proof incomplete: '+slug)
        results[slug]['saved']={'command':' '.join(cmd),'log':saved_log.name,
                                'sha256':sha(saved_log)}
        print('passed',slug,'saved-only',flush=True)
    for entry in manifest['cases']:
        slug=entry['case_id'].removeprefix(HERE.name+'__')
        data=results[slug]
        entry['offline']=data['primary']['offline']
        entry['compatibility']=data['primary']['compatibility']
        entry['negative']={'log':data['primary']['compatibility']['negative_log']}
        entry['candidates'][0]['offline']=data['fallback1']['offline']
        entry['candidates'][0]['compatibility']=data['fallback1']['compatibility']
        entry['saved_replay']=data['saved']
        entry['post_capture']={'command':'.venv-cpu/bin/python runtime.py process-saved --manifest work/'+HERE.name+'/execution-manifest.json --case '+entry['case_id']+' --attempt $ATTEMPT --output $PROCESSED --library runtime/library --validator $LEAN_VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT',
            'feedback_command':'.venv-cpu/bin/python work/'+HERE.name+'/delivery_audit.py --case '+entry['case_id']+' --attempt $ATTEMPT --review $PIXEL_REVIEW --physical $PHYSICAL_RESULT',
            'recorded_only':True,'test_exit_code':0,
            'test_log':data['saved']['log'],'test_log_sha256':data['saved']['sha256']}
    write(MANIFEST,manifest)
    print('all exact runtime CPU proofs passed',len(manifest['cases']))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--tag',required=True)
    args=parser.parse_args()
    main(args.tag)
