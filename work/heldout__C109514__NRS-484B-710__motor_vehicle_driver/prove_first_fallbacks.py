"""Run exact offline and source-bound compatibility checks for three alternatives."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

folder = Path(__file__).resolve().parent
repo = folder.parents[1]
manifest_path = folder / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
entry = manifest['cases'][0]
case = entry['case_id']
entry['candidates'] = json.loads((folder / 'first-fallbacks.json').read_text())
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for candidate in entry['candidates']:
    ident = candidate['id']
    offline_output = repo / '.runtime-work' / ('c109514-exception-source-'+ident+'-offline')
    command = ['.venv-cpu/bin/python','runtime.py','offline','--manifest',str(manifest_path.relative_to(repo)),
               '--case',case,'--candidate',ident,'--output',str(offline_output.relative_to(repo)),
               '--python',str(repo / '.venv-cpu/bin/python')]
    completed = subprocess.run(command, cwd=repo, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, check=False)
    log = folder / ('first-'+ident+'-offline.log')
    log.write_text(completed.stdout)
    if completed.returncode:
        raise ValueError(ident+' offline failed: '+completed.stdout[-800:])
    candidate['offline'] = {'command':' '.join(command),'exit_code':0,'log':log.name,
                            'log_sha256':sha(log),'construction_sha256':candidate['construction_sha256']}
    compat_output = repo / '.runtime-work' / ('c109514-exception-source-'+ident+'-compat')
    command = ['.venv-cpu/bin/python','runtime.py','compatibility','--manifest',str(manifest_path.relative_to(repo)),
               '--case',case,'--candidate',ident,'--output',str(compat_output.relative_to(repo)),
               '--library','runtime/library','--validator','.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    completed = subprocess.run(command, cwd=repo, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, check=False)
    log = folder / ('first-'+ident+'-compat.log')
    log.write_text(completed.stdout)
    if completed.returncode:
        raise ValueError(ident+' compatibility failed: '+completed.stdout[-800:])
    receipt = folder / ('first-'+ident+'-compatibility.json')
    negative = folder / ('first-'+ident+'-negative.log')
    shutil.copy2(compat_output / 'compatibility.json', receipt)
    shutil.copy2(compat_output / 'negative-analysis.log', negative)
    candidate['compatibility'] = {'receipt':receipt.name,'sha256':sha(receipt),
                                  'log':log.name,'negative_log':negative.name}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(ident, 'offline and positive/negative compatibility passed')
