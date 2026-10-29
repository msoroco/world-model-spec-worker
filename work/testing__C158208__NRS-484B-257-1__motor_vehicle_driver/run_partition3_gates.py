"""Execute CPU-only exact gates and bind their small receipts for partition 3."""
import hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
IDS=json.loads((REPO/'partitions/demo-test-03.json').read_text())['assignment_ids']
PY=REPO/'.venv-cpu/bin/python';LOCK=REPO/'.runtime-work/runtime.lock'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def run(cmd,log=None,env=None):
    args=['flock',str(LOCK)]+[str(x) for x in cmd]
    result=subprocess.run(args,cwd=REPO,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if log is not None:Path(log).write_text(result.stdout)
    if result.returncode:raise RuntimeError('Command failed '+str(result.returncode)+': '+' '.join(map(str,cmd))+'\n'+result.stdout[-3000:])
    return result
runtime=REPO/'.runtime-work/partition3';runtime.mkdir(parents=True,exist_ok=True)
(REPO/'.runtime-work/tmp').mkdir(parents=True,exist_ok=True)
for aid in IDS:
    folder=REPO/'work'/aid;manifest=json.loads((folder/'execution-manifest.json').read_text());entry=manifest['cases'][0];case=entry['case_id']
    receipt_dir=folder/'receipts';receipt_dir.mkdir(exist_ok=True)
    env=dict(os.environ,PYTHONPATH=str(REPO/'.runtime-work/overlay/scenario_pipeline'),TMPDIR=str(REPO/'.runtime-work/tmp'),PYTHONDONTWRITEBYTECODE='1')
    testcmd=[PY,'-m','unittest','discover','-s',folder/'tests','-v']
    run(testcmd,receipt_dir/'cpu-tests.log',env)
    offline=runtime/('offline-'+aid+'-'+str(time.time_ns()))
    offcmd=[PY,REPO/'runtime.py','offline','--manifest',folder/'execution-manifest.json','--case',case,'--output',offline]
    run(offcmd,offline.with_suffix('.command.log'),env)
    shutil.copyfile(offline/'offline.log',receipt_dir/'offline.log')
    entry['offline']={'command':' '.join(str(x.relative_to(REPO)) if isinstance(x,Path) and REPO in x.parents else str(x) for x in offcmd),'exit_code':0,'log':'receipts/offline.log','log_sha256':sha(receipt_dir/'offline.log'),'construction_sha256':entry['construction_sha256']}
    compatibility=runtime/('compat-'+aid+'-'+str(time.time_ns()))
    compcmd=[PY,REPO/'runtime.py','compatibility-recipe','--manifest',folder/'execution-manifest.json','--case',case,'--output',compatibility,'--library',REPO/'runtime/main-pipeline-v1/library','--validator',REPO/'.runtime-work/decoder-build/.lake/build/bin/adapterCheck']
    run(compcmd,compatibility.with_suffix('.command.log'),env)
    for src,dst in [('compatibility.json','compatibility.json'),('compatibility-analysis.log','analysis.log'),('negative-analysis.log','negative-analysis.log')]:shutil.copyfile(compatibility/src,receipt_dir/dst)
    entry['compatibility']={'receipt':'receipts/compatibility.json','sha256':sha(receipt_dir/'compatibility.json'),'log':'receipts/analysis.log','command':' '.join(str(x.relative_to(REPO)) if isinstance(x,Path) and REPO in x.parents else str(x) for x in compcmd),'exit_code':0}
    entry['negative']={'log':'receipts/negative-analysis.log','sha256':sha(receipt_dir/'negative-analysis.log')}
    write(folder/'execution-manifest.json',manifest)
    assignment=json.loads((REPO/'inputs'/aid/'assignment.json').read_text())
    gpu=f'python3.11 runtime.py capture --manifest work/{aid}/execution-manifest.json --case {case} --output .runtime-work/attempt-{aid} --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"'
    result={'assignment_id':aid,'input_sha256':sha(REPO/'inputs'/aid/'assignment.json'),'status':'ready','applied_update':1,'readiness_kind':'capability','reason':'CPU-compatible exact case; native motion, original pixels and legal conclusions await local GPU review','first_gpu_capability_command':gpu,'tests':[{'command':'PYTHONPATH=.runtime-work/overlay/scenario_pipeline .venv-cpu/bin/python -m unittest discover -s work/'+aid+'/tests -v','exit_code':0,'log':'receipts/cpu-tests.log','sha256':sha(receipt_dir/'cpu-tests.log')}],'offline_log_sha256':entry['offline']['log_sha256'],'compatibility_receipt_sha256':entry['compatibility']['sha256'],'limitations':['No CARLA or physical acceptance claimed.','Diagnostic fixture measurements are not test evidence of physical behavior.']}
    write(folder/'result.json',result)
    (folder/'HANDOFF.md').write_text('# Exact CPU capability handoff\n\nAssignment: `'+aid+'`\n\nSelected branch: '+assignment['branch']+'\n\nOffline log SHA-256: `'+entry['offline']['log_sha256']+'`\n\nCompatibility receipt SHA-256: `'+entry['compatibility']['sha256']+'`\n\nFirst GPU capability command:\n\n```sh\n'+gpu+'\n```\n\nReview native topology, actor class/width, sign and crosswalk inventory, original ray samples and pixels, controller outcome and legal judgments. The diagnostic fixture proves software compatibility only.\n')
    print(aid,'ready',entry['offline']['log_sha256'],entry['compatibility']['sha256'],flush=True)
