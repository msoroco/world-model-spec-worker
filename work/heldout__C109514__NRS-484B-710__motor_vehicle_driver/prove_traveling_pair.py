"""Prove 499/501 ft exact constructions and each risk-triggered fallback."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

folder = Path(__file__).resolve().parent
repo = folder.parents[1]
path = folder / 'execution-manifest.json'
manifest = json.loads(path.read_text())

def sha(item): return hashlib.sha256(item.read_bytes()).hexdigest()

for entry in manifest['cases']:
    if not entry['case_id'].endswith(('__traveling_follow_499ft','__traveling_follow_501ft')):
        continue
    target = entry['case_id'].split('_')[-1]
    case_folder = folder / 'cases' / ('traveling_follow_'+target)
    for candidate_id, row in [('primary', entry), *[(c['id'], c) for c in entry['candidates']]]:
        base = 'c109514-'+target+'-'+candidate_id
        offline_output = '.runtime-work/'+base+'-offline'
        command = ['.venv-cpu/bin/python','runtime.py','offline','--manifest','work/'+folder.name+'/execution-manifest.json',
                   '--case',entry['case_id'],'--candidate',candidate_id,'--output',offline_output,
                   '--python',str(repo/'.venv-cpu/bin/python')]
        completed = subprocess.run(command,cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=False)
        log = case_folder/(candidate_id+'-offline.log');log.write_text(completed.stdout)
        if completed.returncode:
            raise ValueError(base+' offline failed: '+completed.stdout[-900:])
        row['offline']={'command':' '.join(command),'exit_code':0,'log':str(log.relative_to(folder)),
                        'log_sha256':sha(log),'construction_sha256':row['construction_sha256']}
        compat_output = repo/'.runtime-work'/(base+'-compat')
        command = ['.venv-cpu/bin/python','runtime.py','compatibility','--manifest','work/'+folder.name+'/execution-manifest.json',
                   '--case',entry['case_id'],'--candidate',candidate_id,'--output',str(compat_output.relative_to(repo)),
                   '--library','runtime/library','--validator','.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
        completed=subprocess.run(command,cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=False)
        command_log=case_folder/('compat-command-'+candidate_id+'.log');command_log.write_text(completed.stdout)
        if completed.returncode:
            raise ValueError(base+' compatibility failed: '+completed.stdout[-900:])
        analysis_log=case_folder/('compat-'+candidate_id+'.log')
        negative=case_folder/('negative-'+candidate_id+'.log')
        receipt=case_folder/(candidate_id+'-compatibility.json')
        shutil.copy2(compat_output/'compatibility-analysis.log',analysis_log)
        shutil.copy2(compat_output/'negative-analysis.log',negative)
        shutil.copy2(compat_output/'compatibility.json',receipt)
        row['compatibility']={'receipt':str(receipt.relative_to(folder)),'sha256':sha(receipt),
                              'log':str(analysis_log.relative_to(folder)),'negative_log':str(negative.relative_to(folder))}
        if candidate_id=='primary':
            entry['negative']={'log':str(negative.relative_to(folder))}
        path.write_text(json.dumps(manifest,indent=2)+'\n')
        print(target,candidate_id,'offline and compatibility passed')
