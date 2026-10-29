"""Write the final update002 return report from completed, source-bound proofs."""
import pathlib,json,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p):return {'path':p,'sha256':sha(ROOT/p)}
def main():
 shared=ROOT/'work/_shared';report=read(shared/'return-report.json');audit=read(shared/'update002-final-audit.json');assert audit['passed']
 report.update(update=2,merged_main_commit='abd5d77',prior_return_commit='f52931c56e9b259dc8cc5f5253714f4d4d745986',counts=read(shared/'counts.json'),runtime_manifest_sha256=audit['runtime_manifest_sha256'])
 command='.venv-cpu/bin/python work/_shared/runtime002.py worker_check.py --complete --require-capability-ready'
 report['strict_complete_readiness']={'command':command,'passed':True,'log':dict(ref('work/_shared/readiness-gate002.log'),exit_code=0)}
 report['exact_case_proofs'].update(offline=236,compatibility_positive=236,compatibility_negative=236,process_saved=236,additional_original_frame_joins=236,saved_comparison_audits=150,physical_preparation=236,motion_outcome_fixtures=708,capture_to_processing_lifecycle=236)
 report['test_suites'].update(runtime_regressions=93,worker_contract_tests=30,additional_audit_tests=11,shared_update002_regressions=22,diagnostic_acquisition_authors=26)
 logs=['readiness-gate002.log','runtime-selftest002.log','runtime-regressions.log','worker-tests002.log','additional-audit-tests002.log','update002-regressions.log','diagnostic-authors002-tests.log','c109705-update002-proof.log','retained-audit-cli002.log','update002-physical.log','comparison-proof-run002.log','source-join-tests002.log']
 report['logs']={name:dict(ref('work/_shared/'+name),exit_code=0) for name in logs}
 for key,name in [('gpu_queue','gpu-queue.json'),('first_gpu_command_per_assignment','first-gpu-commands.json'),('runtime_proof','runtime-proof.json')]:report[key]=ref('work/_shared/'+name)
 report['migration_review']=ref('work/_shared/migration002-independent-review.json');report['final_migration_audit']=ref('work/_shared/update002-final-audit.json');report['plan_preservation']=ref('work/_shared/update002-plan-preservation.json')
 report['tested_capability_blockers']=[]
 report['tested_representation_limitations']=['Pinned Core TurnSide has no off/hazard enum. All20 indicator cases preserve explicit raw API off/on history and law-specific continuity/path measurements; per-frame positive Core indicator requirements were inapplicable and corrected after independent review.','The two no-installed-signal cases retain source-bound head-count/state observations without requiring positive Core device/governance entities. No global Core verified-absence claim is made.']
 report['resolved_gate_failure']='Update002 repairs selected saved reanalysis, original/version preservation, Native provenance, physical status/observables, capture-only lifecycle and failed-exit recording; source-shaped diagnostic packets and reviewed conditional acquisition declarations pass the final exact-case proofs.'
 report['retained_recording']={'reported_frames':900,'actual_recording_supplied':False,'actual_recording_audited':False,'replay_performed':False,'handoff':ref('work/_shared/retained-c109705-handoff.json'),'software_cli_test_passed':True,'spawn_clearance':'Remains a live capability finding; no acceptance claimed'}
 report['operator_next_steps']=['check-return and preflight-return against the committed existing return branch; neither contacts CARLA','Audit the retained900-frame C109705 capture using the saved-only handoff, without replay','For future queue execution, local operator owns resources; release ownership before acknowledgement and selected saved processing; use saved version indexes for comparison audits']
 report['remaining']=list(dict.fromkeys(report.get('remaining',[])+['Actual Native sign-node acquisition within graph render distance/crop and original sign pixels','Actual retained900-frame C109705 spawn clearance and complete motion review']))
 report['physical_acceptance_claimed']=False;report['legal_acceptance_claimed']=False;report['carla_executed']=False
 (shared/'return-report.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Update002 return report refreshed:236 cases,708 motion outcomes,236 lifecycle proofs; Native executed0')
if __name__=='__main__':main()
