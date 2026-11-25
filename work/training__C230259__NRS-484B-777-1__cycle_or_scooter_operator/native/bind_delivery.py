"""Bind independent exact delivery source audits without physical claims."""
import hashlib,json
from pathlib import Path
F=Path(__file__).resolve().parent.parent;M=F/'execution-manifest.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads(M.read_text())
script=F/'delivery_acceptance.py'
for e in m['cases']:
 label=e['case_id'].rsplit('__',1)[-1]; cid=e['case_id']
 positive=f'delivery-{label}-positive';negative=f'delivery-{label}-negative'
 e['delivery_acceptance']={'case_id':cid,'sets':['full-train'],
  'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],
  'script':'delivery_acceptance.py','script_sha256':sha(script),
  'command':f'.venv-cpu/bin/python work/{F.name}/delivery_acceptance.py --attempt .runtime-work/c230259-compat/sealed-{label}-primary --case {cid} --diagnostic --output work/{F.name}/{positive}.json',
  'test_exit_code':0,'test_log':positive+'.log','test_log_sha256':sha(F/(positive+'.log')),
  'negative_command':f'.venv-cpu/bin/python work/{F.name}/delivery_acceptance.py --attempt .runtime-work/c230259-compat/sealed-{label}-primary --case {cid} --output work/{F.name}/{negative}.json',
  'negative_exit_code':1,'negative_expected_error':'Missing delivery source: capture-seal.json',
  'negative_log':negative+'.log','negative_log_sha256':sha(F/(negative+'.log')),
  'proof_scope':'Synthetic source join and synthetic-as-physical rejection only'}
M.write_text(json.dumps(m,indent=2)+'\n')
plan=F/'case-plan.json';p=json.loads(plan.read_text())
p['comparisons'][0]['status']='diagnostic_independent_audit_passed_physical_pending'
p['comparisons'][0]['audit']={'report':'comparison-main-audit.json','sha256':sha(F/'comparison-main-audit.json'),
 'log':'comparison-main-audit.log','log_sha256':sha(F/'comparison-main-audit.log')}
plan.write_text(json.dumps(p,indent=2)+'\n')
print(json.dumps({'delivery_cases':2,'comparison_delta_m':json.loads((F/'comparison-main-audit.json').read_text())['observed_margin_delta_m']}))
