"""Reprove all selected candidates after a canonical case-proposal change."""
import hashlib
import json
import shlex
import shutil
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
manifest_path = folder/'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w') as out:
        subprocess.run(args,cwd=repo,stdout=out,stderr=subprocess.STDOUT,check=True)


proofs=[]
for entry in manifest['cases']:
    case=entry['case_id']
    label='yield' if case.endswith('__reciprocal_yield_after_turn') else 'continues'
    for candidate,item in [('primary',entry)]+[(c['id'],c) for c in entry['candidates']]:
        prefix=f'c109749-semantic-{label}-{candidate}'
        compat=repo/'.runtime-work'/(prefix+'-compat-v1')
        saved=repo/'.runtime-work'/(prefix+'-saved-v1')
        args=[str(repo/'.venv-cpu/bin/python'),'runtime.py','compatibility',
              '--manifest',str(manifest_path.relative_to(repo)),'--case',case,
              '--output',str(compat.relative_to(repo)),'--library','runtime/library',
              '--validator','.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck']
        if candidate!='primary':args+=['--candidate',candidate]
        log = folder/('primary-compatibility.log' if label=='yield' and candidate=='primary'
                      else f'cases/{candidate}-compatibility.log' if label=='yield'
                      else f'cases/reciprocal_continues/{candidate}-compatibility.log')
        run(args,log)
        spec=item['compatibility']
        shutil.copyfile(compat/'compatibility.json',folder/spec['receipt'])
        shutil.copyfile(compat/'compatibility-analysis.log',folder/spec['log'])
        shutil.copyfile(compat/'negative-analysis.log',folder/spec['negative_log'])
        saved_args=[str(repo/'.venv-cpu/bin/python'),'runtime.py','process-saved',
                    '--manifest',str(manifest_path.relative_to(repo)),'--case',case,
                    '--attempt',str(compat.relative_to(repo)),'--output',str(saved.relative_to(repo)),
                    '--library','runtime/library',
                    '--validator','.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck']
        saved_log=folder/item['post_capture']['test_log']
        run(saved_args,saved_log)
        if candidate=='primary':
            saved_receipt=(folder/'primary-saved-processing.json' if label=='yield'
                           else folder/'cases/reciprocal_continues/primary-saved-processing.json')
            shutil.copyfile(saved/'v0001/processing.json',saved_receipt)
        proofs.append((item,prefix,shlex.join(args),shlex.join(saved_args),log,saved_log))
        print('passed',label,candidate,flush=True)

for item,prefix,compat_command,saved_command,log,saved_log in proofs:
    item['compatibility']['sha256']=sha(folder/item['compatibility']['receipt'])
    item['compatibility']['replay_command']=compat_command
    item['compatibility']['replay_log']=str(log.relative_to(folder))
    item['post_capture']['command']=saved_command
    item['post_capture']['test_log_sha256']=sha(saved_log)
    item['post_capture']['feedback_command']='cat .runtime-work/'+prefix+'-saved-v1/v0001/feedback.json'
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
print('all eight compatibility and saved receipts rebound',flush=True)
