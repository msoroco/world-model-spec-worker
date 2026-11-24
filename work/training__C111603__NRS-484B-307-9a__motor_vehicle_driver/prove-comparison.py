"""Recheck selected movement contrast and reject one changed fixed source."""
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c111603-rebound'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
case1=HERE.name+'__witness_1';case2=HERE.name+'__witness_2'
first=SCRATCH/'witness_1-primary-compat-v2';second=SCRATCH/'witness_2-primary-compat-v2'
report1=first/'analysis-report.json';report2=second/'analysis-report.json'
out=HERE/'selected-comparison-audit.json';positive=HERE/'selected-comparison-positive.log';negative=HERE/'selected-comparison-negative.log'
base=[sys.executable,str(HERE/'selected-comparison-audit.py'),'--first-report',str(report1),'--second-report',str(report2),'--second',str(second),'--output',str(out)]
cmd=base+['--first',str(first)]
proc=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
positive.write_text(proc.stdout.rstrip()+'\n')
if proc.returncode:raise RuntimeError(proc.stdout[-1000:])
changed=SCRATCH/'comparison-changed-source';changed.mkdir(parents=True,exist_ok=True)
raw=[json.loads(line) for line in (first/'native-raw-actors.jsonl').read_text().splitlines()]
raw[0]['red_state']='Green'
(changed/'native-raw-actors.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in raw))
cmd_negative=base+['--first',str(changed)]
failure=subprocess.run(cmd_negative,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
negative.write_text(failure.stdout.rstrip()+'\n')
expected='Comparison source hash changed: native-raw-actors.jsonl'
if failure.returncode==0 or expected not in failure.stdout:raise RuntimeError('Comparison drift not rejected')
manifest=json.loads((HERE/'execution-manifest.json').read_text())
for entry in manifest['cases']:
 entry['comparison_audit']={'script':'selected-comparison-audit.py','script_sha256':sha(HERE/'selected-comparison-audit.py'),
  'command':f'.venv-cpu/bin/python work/{HERE.name}/selected-comparison-audit.py --first {first} --second {second} --first-report {report1} --second-report {report2} --output {out}',
  'test_log':str(positive.relative_to(HERE)),'test_log_sha256':sha(positive),'test_exit_code':0,
  'negative_command':f'.venv-cpu/bin/python work/{HERE.name}/selected-comparison-audit.py --first {changed} --second {second} --first-report {report1} --second-report {report2} --output {out}',
  'negative_log':str(negative.relative_to(HERE)),'negative_log_sha256':sha(negative),
  'negative_exit_code':failure.returncode,'negative_expected_error':expected}
(HERE/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'comparison_sha256':sha(out),'manifest_sha256':sha(HERE/'execution-manifest.json')}))
