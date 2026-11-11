"""CPU-test and bind nine exact independent source-audit acceptance contracts."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
AUDITOR = ROOT / 'rider_acceptance_check.py'
ATTEMPTS = {
 'bicycle_signal_once': '.runtime-work/c111588-common-bicycle_signal_once-primary-compat-j',
 'bicycle_no_signal': '.runtime-work/c111588-common-bicycle_no_signal-primary-compat-j',
 'bicycle_signal_continuous': '.runtime-work/c111588-common-bicycle_signal_continuous-primary-compat-j',
 'electric_bicycle_signal_once': '.runtime-work/c111588-common-electric_bicycle_signal_once-primary-compat-j',
 'electric_scooter_signal_once': '.runtime-work/c111588-common-electric_scooter_signal_once-primary-compat-j',
 'turn_lane_no_signal': '.runtime-work/c111588-common-turn_lane_no_signal-primary-compat-j',
 'both_hands_no_signal': '.runtime-work/c111588-common-both_hands_no_signal-primary-compat-j',
 'safety_wide': '.runtime-work/c111588-common-safety_wide-primary-compat-j',
 'safety_narrow': '.runtime-work/c111588-common-safety_narrow-primary-compat-j',
}

def sha(path):
 return sha256(path.read_bytes()).hexdigest()

manifest_path=ROOT/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())
for entry in manifest['cases']:
 case=entry['case_id'];slug=case.rsplit('__',1)[-1]
 folder=ROOT/'cases'/slug/'physical';folder.mkdir(exist_ok=True)
 base=f'PYTHONPATH=runtime/scenario_pipeline {PY} work/{ROOT.name}/rider_acceptance_check.py --case {case} --attempt {ATTEMPTS[slug]}'
 env={**os.environ,'PYTHONPATH':'runtime/scenario_pipeline'}
 command=[PY,str(AUDITOR),'--case',case,'--attempt',ATTEMPTS[slug]]
 positive=subprocess.run(command,cwd=REPO,env=env,text=True,capture_output=True)
 positive_log=folder/'acceptance-positive.log';positive_log.write_text(positive.stdout+positive.stderr)
 if positive.returncode:raise RuntimeError(slug+' positive: '+positive_log.read_text()[-1200:])
 negative=subprocess.run([*command,'--negative'],cwd=REPO,env=env,text=True,capture_output=True)
 negative_log=folder/'acceptance-negative.log';negative_log.write_text(negative.stdout+negative.stderr)
 error='Stale or missing original source: rider_arm_bones.jsonl'
 if negative.returncode==0 or error not in negative_log.read_text():
  raise RuntimeError(slug+' negative: '+negative_log.read_text()[-1200:])
 entry['delivery_acceptance']={'case_id':case,'sets':['held-out'],
   'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],
   'script':'rider_acceptance_check.py','script_sha256':sha(AUDITOR),
   'command':base,'test_exit_code':0,
   'test_log':str(positive_log.relative_to(ROOT)),'test_log_sha256':sha(positive_log),
   'negative_command':base+' --negative','negative_exit_code':negative.returncode,
   'negative_expected_error':error,'negative_log':str(negative_log.relative_to(ROOT)),
   'negative_log_sha256':sha(negative_log)}
 print(slug,'positive and stale-original audit passed',flush=True)
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
