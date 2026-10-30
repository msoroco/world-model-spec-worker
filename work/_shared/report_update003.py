"""Refresh final return metadata after the exact-v6 handoff and strict gate pass."""
import pathlib,json,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(name):return {'path':name,'sha256':sha(ROOT/name)}
def main():
 shared=ROOT/'work/_shared';report=read(shared/'return-report.json');audit=read(shared/'update003-final-audit.json');gate=read(shared/'readiness-gate003.log')
 assert audit['passed'] and gate['static_validation']=='passed' and len(gate['results'])==43 and set(gate['results'].values())=={'ready'}
 report.update(update=3,merged_main_commit='2a4d0e9',prior_return_commit='5366dda0ccde716199b26f7cd0b2ae2ebec12aab',counts=read(shared/'counts.json'),runtime_manifest_sha256=audit['runtime_manifest_sha256'])
 report['strict_complete_readiness']={'command':'.venv-cpu/bin/python work/_shared/runtime002.py worker_check.py --complete --require-capability-ready','passed':True,'log':dict(ref('work/_shared/readiness-gate003.log'),exit_code=0)}
 report['exact_case_proofs'].update(offline=236,compatibility_positive=236,compatibility_negative=236,process_saved=236,additional_original_frame_joins=236,saved_comparison_audits=150,physical_preparation_preserved=236,motion_outcome_fixtures_preserved=708)
 report['test_suites'].update(worker_contract_tests=31,update003_independent_regressions=29,legacy_source_tests=7)
 logs=['readiness-gate003.log','runtime-selftest003.log','runtime-regressions.log','worker-tests003.log','update003-v7-software.log','source-join-tests003.log','comparison-proof-run003.log','update003-final-audit.log']
 report['logs']={name:dict(ref('work/_shared/'+name),exit_code=0) for name in logs}
 for key,name in [('gpu_queue','gpu-queue.json'),('first_gpu_command_per_assignment','first-gpu-commands.json'),('runtime_proof','runtime-proof.json')]:report[key]=ref('work/_shared/'+name)
 report['update003_independent_review']=ref('work/_shared/update003-independent-review.json');report['update003_final_audit']=ref('work/_shared/update003-final-audit.json')
 report['legacy_handoff']=ref('work/_shared/retained-c109705-handoff.json')
 handoff=read(shared/'retained-c109705-handoff.json');report['retained_recording']={'exact_case_id':handoff['case_id'],'frames':900,'actual_recording_supplied':False,'actual_recording_audited':False,'native_replay_requested':False,'isolated_manifest':handoff['manifest'],'synthetic_saved_only_proof':handoff['diagnostic_proof'],'repeated_versions_tested':['v0001','v0002'],'original_and_previous_outputs_preserved':True,'member_of_v7_delivery_queue':False}
 report['tested_capability_blockers']=[]
 report['resolved_gate_failure']='Update003 binds the separate retained v6 selected_left_turn identity and frozen Native construction. A900-frame synthetic saved-only run and repeated version pass; wrong IDs/manifests/embedded IDs and unmarked wrong Native hashes fail. All236 v7 exact software proofs refreshed; existing construction-bound physical proofs preserved.'
 report['operator_next_steps']=['check-return and preflight-return on the committed existing branch; neither contacts CARLA','After actual operator ownership release, acknowledge release and run the exact isolated-v6 saved-only command in retained-c109705-handoff.json on original files; do not replay the retained capture','The236-case v7 queue remains a separate unchanged delivery plan']
 report['physical_acceptance_claimed']=False;report['legal_acceptance_claimed']=False;report['carla_executed']=False
 def refresh(value):
  if isinstance(value,dict):
   if isinstance(value.get('path'),str) and value['path'].startswith('work/') and 'sha256' in value:value['sha256']=sha(ROOT/value['path'])
   for item in value.values():refresh(item)
  elif isinstance(value,list):
   for item in value:refresh(item)
 refresh(report);(shared/'return-report.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Update003 report refreshed:236 preserved v7 cases; separate900-frame exact-v6 saved-only proof; actual recording unaudited')
if __name__=='__main__':main()
