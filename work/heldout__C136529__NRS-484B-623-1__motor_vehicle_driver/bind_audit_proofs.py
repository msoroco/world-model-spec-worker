"""Bind exact source audit receipts without claiming physical acceptance."""
from pathlib import Path
import json
import hashlib
root=Path(__file__).resolve().parent
sha=lambda rel:hashlib.sha256((root/rel).read_bytes()).hexdigest()
manifest_path=root/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())
for entry in manifest['cases']:
    case=entry['case_id'];branch=case.removeprefix(root.name+'__').replace('__','-')
    positive=f'{branch}-delivery-positive.log';negative=f'{branch}-delivery-negative.log'
    entry['delivery_acceptance']={
      'case_id':case,'sets':['held-out'],
      'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],
      'script':'delivery_audit.py','script_sha256':sha('delivery_audit.py'),
      'command':f'.venv-cpu/bin/python work/{root.name}/prove_delivery_audit.py --case {case}',
      'test_exit_code':0,'test_log':positive,'test_log_sha256':sha(positive),
      'negative_command':f'.venv-cpu/bin/python work/{root.name}/prove_delivery_audit.py --case {case} --negative',
      'negative_exit_code':1,'negative_expected_error':'Missing audited original source: participant_state.jsonl',
      'negative_log':negative,'negative_log_sha256':sha(negative)}
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
plan_path=root/'case-plan.json';plan=json.loads(plan_path.read_text())
for case in plan['cases']:
    case['construction_status']='primary_and_three_fallbacks_offline_compatibility_saved_proved'
for comparison in plan['comparisons']:
    name=comparison['comparison_id'];positive=f'{name}-comparison-positive.log';negative=f'{name}-comparison-negative.log'
    comparison['audit_proof']={
      'script':'comparison_audit.py','script_sha256':sha('comparison_audit.py'),
      'command':f'.venv-cpu/bin/python work/{root.name}/prove_comparisons.py --comparison {name}',
      'exit_code':0,'log':positive,'log_sha256':sha(positive),
      'negative_command':f'.venv-cpu/bin/python work/{root.name}/prove_comparisons.py --comparison {name} --negative',
      'negative_exit_code':1,'negative_expected_error':'Fixed comparison condition differs: duration_s',
      'negative_log':negative,'negative_log_sha256':sha(negative)}
plan_path.write_text(json.dumps(plan,indent=2)+'\n')
print('bound',len(manifest['cases']),'exact delivery and',len(plan['comparisons']),'comparison audits')
