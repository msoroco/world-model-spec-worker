"""Exact offline and compatibility proof for all nine common-source rider bundles."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
PY=str(REPO/'.venv-cpu/bin/python')
PREFIX='heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__'
MANIFESTS={'bicycle_signal_once':'first-execution-manifest.json',
 'bicycle_no_signal':'no-signal-manifest.json','bicycle_signal_continuous':'continuous-manifest.json',
 'electric_bicycle_signal_once':'electric-bicycle-manifest.json','electric_scooter_signal_once':'electric-scooter-manifest.json',
 'turn_lane_no_signal':'turn-lane-manifest.json','both_hands_no_signal':'both-hands-manifest.json',
 'safety_wide':'safety-wide-manifest.json','safety_narrow':'safety-narrow-manifest.json'}
def sha(path):return sha256(path.read_bytes()).hexdigest()
def run(cmd,log):
 with log.open('w') as out: result=subprocess.run(cmd,cwd=REPO,stdout=out,stderr=subprocess.STDOUT)
 if result.returncode:raise RuntimeError(str(cmd)+'\n'+log.read_text()[-1600:])
for slug,manifest_name in MANIFESTS.items():
 case=PREFIX+slug;manifest=ROOT/manifest_name;folder=ROOT/'cases'/slug
 obj=json.loads(manifest.read_text());entry=obj['cases'][0]
 for i in range(4):
  name='primary' if i==0 else 'fallback'+str(i);candidate=[] if i==0 else ['--candidate',name]
  off=f'.runtime-work/c111588-common-{slug}-{name}-offline-j'
  off_cmd=[PY,'runtime.py','offline','--manifest',str(manifest.relative_to(REPO)),
   '--case',case,'--output',off,'--python',PY]+candidate
  off_log=folder/(name+'-tests-j.log');run(off_cmd,off_log)
  compat=f'.runtime-work/c111588-common-{slug}-{name}-compat-j'
  compat_cmd=[PY,'runtime.py','compatibility','--manifest',str(manifest.relative_to(REPO)),
   '--case',case,'--output',compat,'--library','runtime/library',
   '--validator','.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']+candidate
  stdout=folder/(name+'-stdout-j.log');run(compat_cmd,stdout)
  receipt=folder/(name+'-receipt-j.json');analysis=folder/(name+'-analysis-j.log');negative=folder/(name+'-negative-j.log')
  shutil.copy2(REPO/compat/'compatibility.json',receipt)
  shutil.copy2(REPO/compat/'compatibility-analysis.log',analysis)
  shutil.copy2(REPO/compat/'negative-analysis.log',negative)
  if i:
   item=entry['candidates'][i-1]
   item['offline']={'command':' '.join(off_cmd),'exit_code':0,'log':str(off_log.relative_to(ROOT)),
                    'log_sha256':sha(off_log),'construction_sha256':item['construction_sha256']}
   item['compatibility']={'receipt':str(receipt.relative_to(ROOT)),'sha256':sha(receipt),
                          'log':str(analysis.relative_to(ROOT)),'negative_log':str(negative.relative_to(ROOT))}
  print(slug,name,'offline/compatibility passed',flush=True)
 manifest.write_text(json.dumps(obj,indent=2)+'\n')
