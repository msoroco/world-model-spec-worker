"""Publish exact CPU-proven preparation status, without physical acceptance."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
result_path=HERE/'result.json';result=json.loads(result_path.read_text())
manifest=json.loads((HERE/'execution-manifest.json').read_text())
selected=json.loads((HERE/'selected-v2-manifest.json').read_text())
assert len(manifest['cases'])==2
for entry in manifest['cases']:
 assert len(entry['candidates'])==2
 for candidate in [entry,*entry['candidates']]:
  assert candidate['offline']['exit_code']==0
  proof=json.loads((HERE/candidate['compatibility']['receipt']).read_text())
  assert proof['passed'] is True
  witness=entry['case_id'].rsplit('__',1)[-1]
  cid='primary' if candidate is entry else candidate['id']
  saved=json.loads((HERE/'selected-runtime-proofs'/witness/cid/'processing.json').read_text())
  assert saved['passed'] is True and saved['recorded_only'] is True
  assert saved['physical_acceptance_claimed'] is False and saved['legal_acceptance_claimed'] is False
log=HERE/'selected-root-tests.log'
assert 'Ran 3 tests' in log.read_text() and '\nOK\n' in log.read_text()
result['status']='ready'
result['readiness_kind']='delivery_prepared'
result['reason']='Two exact source-grounded witness cases with two risk-based fallback plans each have CPU-proven offline, current-runtime public compatibility, missing-source negatives, recorded-only saved processing, semantic stage, comparison, physical-branch and delivery-source audits. Original Native motion, arrow pixels, governing direction, lawful presence and yielding remain for the first local delivery and independent review; no legal or physical acceptance is claimed.'
result['selected_cpu_checkpoint']={'manifest':'selected-v2-manifest.json',
 'manifest_sha256':sha(HERE/'selected-v2-manifest.json'),
 'execution_manifest':'execution-manifest.json','execution_manifest_sha256':sha(HERE/'execution-manifest.json'),
 'selected_cases':[e['case_id'] for e in manifest['cases']],
 'offline_passed':6,'public_compatibility_passed':6,'recorded_only_saved_passed':6,
 'original_source_shape_tests_passed':3,
 'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
result['first_gpu_delivery_command']=f'PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange execute-delivery --repo . --batch full-train-delivery --db $DB --assignment {HERE.name} --case {manifest["cases"][0]["case_id"]} --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT'
result['tests']=[{'command':f'SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c111603-source-shape-tests PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/{HERE.name}/tests -v',
 'exit_code':0,'log':'selected-root-tests.log','sha256':sha(log)}]
for entry in manifest['cases']:
 for candidate in [entry,*entry['candidates']]:
  cid='primary' if candidate is entry else candidate['id']
  for kind,path in (('offline',candidate['offline']['log']),('compatibility',candidate['compatibility']['receipt'])):
   source=HERE/path
   result['tests'].append({'command':f'.venv-cpu/bin/python runtime.py {kind} --manifest work/{HERE.name}/selected-v2-manifest.json --case {entry["case_id"]} --candidate {cid}',
    'exit_code':0,'log':path,'sha256':sha(source)})
result['strict_gate']={'command':f'.venv-cpu/bin/python worker_check.py --assignment {HERE.name} --complete --require-delivery-ready',
 'status':'pending_independent_check'}
result_path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({'result_sha256':sha(result_path),'tests':len(result['tests'])}))
