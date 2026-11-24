"""Retain exact primary diagnostic delivery positives and missing-source negatives."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c111603-rebound'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
manifest=json.loads((HERE/'execution-manifest.json').read_text())
for entry in manifest['cases']:
 case=entry['case_id'];witness=case.rsplit('__',1)[-1]
 attempt=SCRATCH/f'{witness}-primary-compat-v2'
 processing=SCRATCH/f'{witness}-primary-saved-v2/v0001/processing.json'
 dest=HERE/'selected-runtime-proofs'/witness/'primary'
 positive=dest/'delivery-positive.log';negative=dest/'delivery-negative.log';report=dest/'delivery-report.json'
 base=[sys.executable,str(HERE/'delivery_audit.py'),'--case',case,'--candidate','primary',
  '--processing',str(processing),'--output',str(report),'--diagnostic']
 cmd=base+['--attempt',str(attempt)]
 proc=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 positive.write_text(proc.stdout.rstrip()+'\n')
 if proc.returncode:raise RuntimeError('Delivery positive failed: '+proc.stdout[-1000:])
 negdir=SCRATCH/f'{witness}-delivery-negative';negdir.mkdir(parents=True,exist_ok=True)
 select=negdir/'candidate-selection.json'
 if not select.exists():select.symlink_to((attempt/'candidate-selection.json').resolve())
 cmd_negative=base+['--attempt',str(negdir)]
 failure=subprocess.run(cmd_negative,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 negative.write_text(failure.stdout.rstrip()+'\n')
 expected='Missing original source: native-raw-actors.jsonl'
 if failure.returncode==0 or expected not in failure.stdout:raise RuntimeError('Delivery negative did not reject missing source')
 entry['delivery_acceptance']={'case_id':case,'sets':['full-train'],
  'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],
  'script':'delivery_audit.py','script_sha256':sha(HERE/'delivery_audit.py'),
  'command':f'.venv-cpu/bin/python work/{HERE.name}/delivery_audit.py --case {case} --candidate primary --attempt "$ATTEMPT" --processing "$PROCESSING" --output "$REPORT" --diagnostic',
  'negative_command':f'.venv-cpu/bin/python work/{HERE.name}/delivery_audit.py --case {case} --candidate primary --attempt "$MISSING_NATIVE_SOURCE" --processing "$PROCESSING" --output "$REPORT" --diagnostic',
  'test_log':str(positive.relative_to(HERE)),'test_log_sha256':sha(positive),'test_exit_code':0,
  'negative_log':str(negative.relative_to(HERE)),'negative_log_sha256':sha(negative),
  'negative_exit_code':failure.returncode,'negative_expected_error':expected}
(HERE/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'cases':len(manifest['cases']),'manifest_sha256':sha(HERE/'execution-manifest.json')}))
