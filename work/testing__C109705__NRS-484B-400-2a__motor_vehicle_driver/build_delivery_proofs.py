"""Rerun all exact partition-1 offline and diagnostic compatibility proofs under v3."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BATCH=json.loads((ROOT/'batch.json').read_text())
PYTHON=str(ROOT/'.venv-cpu/bin/python')
LAUNCH='work/_shared/runtime-v3.py'
LIBRARY='runtime/main-pipeline-v3/library'
DECODER='.runtime-work/decoder-v3/.lake/build/bin/adapterCheck'

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()

for aid,meta in BATCH['assignments'].items():
 if meta['partition']!=1:continue
 folder=ROOT/'work'/aid
 manifest_path=folder/'execution-manifest.json'
 manifest=json.loads(manifest_path.read_text())
 for index,entry in enumerate(manifest['cases']):
  case=entry['case_id'];slug=case.split('__')[-1]
  base=ROOT/'.runtime-work'/aid/('delivery-v3-'+slug)
  offline_output=base/'offline';compat_output=base/'compat'
  if offline_output.exists():shutil.rmtree(offline_output)
  if compat_output.exists():shutil.rmtree(compat_output)
  offline_cmd=[PYTHON,LAUNCH,'runtime.py','offline','--manifest',str(manifest_path.relative_to(ROOT)),
   '--case',case,'--output',str(offline_output.relative_to(ROOT)),'--python',PYTHON]
  proc=subprocess.run(offline_cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
  if proc.returncode:
   print('OFFLINE FAIL',case,proc.stdout[-1200:],flush=True);raise SystemExit(proc.returncode)
  offline_log=folder/entry['offline']['log']
  shutil.copyfile(offline_output/'offline.log',offline_log)
  entry['offline']={'command':' '.join(offline_cmd),'exit_code':0,
   'log':str(offline_log.relative_to(folder)),'log_sha256':digest(offline_log),
   'construction_sha256':entry['construction_sha256']}
  compat_cmd=[PYTHON,LAUNCH,'runtime.py','compatibility-recipe',
   '--manifest',str(manifest_path.relative_to(ROOT)),'--case',case,
   '--output',str(compat_output.relative_to(ROOT)),'--library',LIBRARY,'--validator',DECODER]
  proc=subprocess.run(compat_cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
  if proc.returncode:
   print('COMPAT FAIL',case,proc.stdout[-1200:],flush=True);raise SystemExit(proc.returncode)
  receipt=folder/'receipts'/('delivery-v3-compat-'+slug+'.json')
  log=folder/'receipts'/('delivery-v3-analysis-'+slug+'.log')
  negative=folder/'receipts'/('delivery-v3-negative-'+slug+'.log')
  command_log=folder/'receipts'/('delivery-v3-command-'+slug+'.log')
  shutil.copyfile(compat_output/'compatibility.json',receipt)
  shutil.copyfile(compat_output/'compatibility-analysis.log',log)
  shutil.copyfile(compat_output/'negative-analysis.log',negative)
  command_log.write_text(proc.stdout)
  entry['compatibility']={'receipt':str(receipt.relative_to(folder)),'sha256':digest(receipt),
    'log':str(log.relative_to(folder)),'log_sha256':digest(log),
    'command':' '.join(compat_cmd),'command_log':str(command_log.relative_to(folder)),
    'command_log_sha256':digest(command_log)}
  entry['negative']={'log':str(negative.relative_to(folder)),'log_sha256':digest(negative)}
  print('PASS',case,flush=True)
 manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
