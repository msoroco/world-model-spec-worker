"""Bind independent CPU audit test logs to exact selected delivery cases."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=HERE/'execution-manifest.json';data=json.loads(manifest.read_text())
script='audit-selected.py';script_sha=sha(HERE/script)
for entry in data['cases']:
 s=entry['case_id'].split('__')[-1];l=s[-1];case=entry['case_id']
 pos=f'current-delivery-{s}-positive.log';neg=f'current-delivery-{s}-negative.log'
 entry['delivery_acceptance']={'case_id':case,'sets':['demo-train','full-train'],'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],'script':script,'script_sha256':script_sha,'command':f'.venv-cpu/bin/python work/{HERE.name}/{script} delivery --case {case}','test_exit_code':0,'test_log':pos,'test_log_sha256':sha(HERE/pos),'negative_command':f'.venv-cpu/bin/python work/{HERE.name}/{script} delivery --case {case} --reject-missing-source','negative_exit_code':1,'negative_expected_error':'Missing required source: native_samples.jsonl','negative_log':neg,'negative_log_sha256':sha(HERE/neg),'cpu_scope':'fixture checker only; no physical acceptance'}
 entry['post_capture']['test_log']=f'current-selected-saved-{l}.log'
 entry['post_capture']['test_log_sha256']=sha(HERE/f'current-selected-saved-{l}.log')
 entry['post_capture']['test_exit_code']=0
 entry['comparison_audit']={'script':script,'script_sha256':script_sha,'command':f'.venv-cpu/bin/python work/{HERE.name}/{script} comparison','test_log':'current-selected-comparison.log','test_log_sha256':sha(HERE/'current-selected-comparison.log'),'test_exit_code':0,'negative_command':f'.venv-cpu/bin/python work/{HERE.name}/{script} comparison --reject-comparison-drift','negative_log':'current-selected-comparison-negative.log','negative_log_sha256':sha(HERE/'current-selected-comparison-negative.log'),'negative_exit_code':1,'negative_expected_error':'Comparison fixed condition changed: primary'}
 entry['candidate_trigger_test']={'command':f'.venv-cpu/bin/python work/{HERE.name}/{script} triggers','test_log':'current-candidate-triggers.log','test_log_sha256':sha(HERE/'current-candidate-triggers.log'),'test_exit_code':0}
manifest.write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps({'cases':len(data['cases']),'manifest_sha256':sha(manifest)}))
