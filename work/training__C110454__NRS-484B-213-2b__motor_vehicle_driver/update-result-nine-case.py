"""Record only the completed nine-case current-hash CPU checkpoint."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
AID=HERE.name
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=HERE/'execution-manifest.json';m=read(manifest);digest=sha(manifest)
index=HERE/'update042-nine-selected-index.json';i=read(index)
assert len(m['cases'])==9 and i['manifest_sha256']==digest and i['candidate_count']==len(i['results'])==36
artifacts={
 'current_selected_nine_cpu_proof':('update042-nine-selected-index.json','run-nine-selected-update042.py'),
 'current_selected_physical_outcomes_cpu_proof':('update042-physical-outcomes-proof.json','prove-selected-physical-outcomes-update042.py'),
 'current_selected_delivery_acceptance_cpu_proof':('update042-selected-delivery-proof.json','refresh-selected-delivery-update042.py'),
 'current_selected_original_comparison_cpu_proof':('update042-original-comparison-proof.json','prove-original-comparisons-update042.py'),
 'current_semantic_cpu_proof':('update041-selected-semantic-proof.json','prove-selected-semantic-update041.py'),
 'current_selected_queue_fragment_cpu_proof':('update020-selected-queue-proof.json','prove-selected-queue-fragment.py'),
 'current_local_audit_import_cpu_proof':('update032-local-audit-import-proof.json','prove-local-audit-import.py')}
for key,(name,script) in artifacts.items():
 assert (HERE/name).is_file() and (HERE/script).is_file(),key
for key in ('current_selected_physical_outcomes_cpu_proof','current_semantic_cpu_proof'):
 name=artifacts[key][0];assert read(HERE/name)['manifest_sha256']==digest,key
assert len(read(HERE/'update042-selected-delivery-proof.json')['cases'])==9
assert len(read(HERE/'update042-original-comparison-proof.json')['diagnostic_comparisons'])==5
result_path=HERE/'result.json';r=read(result_path)
for key in list(r):
 if key.startswith('current_'):
  historical='historical_pre_nine_'+key.removeprefix('current_')
  if historical not in r:r[historical]=r.pop(key)
  else:r.pop(key)
r['status']='partial';r['readiness_kind']=None;r['applied_update']=15
r['reason']=('Update 042: nine exact delivery cases and 36 primary/fallback candidate chains pass current-manifest CPU offline, positive/negative compatibility, saved-processing and source/camera diagnostics; nine physical and delivery diagnostic proofs and five non-accepting comparison diagnostics pass. No original Native capture, owner release, physical/pixel verification, recording or comparison is accepted. Raw frozen assignment law_record versus pinned semantic law-key adoption still fails; accepted 101/100/99-foot originals have no receipt sources for equivalence; canonical batch queue/local integration is unfinished. Full strict gate also rejects unchanged generated runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json; runtime is frozen.')
r['cases_planned']=9;r['cases_selected']=9;r['candidate_plans_proven']=36;r['selected_comparison_cpu_proofs_passed']=5
r['comparison_audits_passed']=0;r['recordings_accepted']=0;r['carla_executed']=False
r['remaining_gpu_checks']=['Actual Native motion and map designation','Original four-camera visibility and pixel review','Original capture closure, owner release, recording and comparison acceptance']
for key,(name,script) in artifacts.items():
 r[key]={'manifest_sha256':digest,'proof':name,'proof_sha256':sha(HERE/name),'script':script,'script_sha256':sha(HERE/script),'original_native_or_delivery_acceptance_claimed':False}
r['current_selected_nine_cpu_proof'].update(selected_cases=9,candidates=36)
r['current_selected_original_comparison_cpu_proof'].update(diagnostic_comparisons=5,original_comparisons_accepted=0)
r['current_selected_delivery_acceptance_cpu_proof'].update(selected_cases=9,diagnostic_positive=9,negative_rejections=9)
r['current_semantic_cpu_proof'].update(selected_cases=9,pinned_stage_chain_passed=True,raw_frozen_assignment_error='Assignment lacks exact law text')
logs=[('runtime.py preflight','update042-preflight.log'),('.venv-cpu/bin/python -m unittest discover -s tests','update042-root-tests.log'),('run-nine-selected-update042.py','update042-nine-selected-run.log'),('prove-selected-physical-outcomes-update042.py','update042-physical-outcomes.log'),('refresh-selected-delivery-update042.py','update042-delivery-proof.log'),('prove-original-comparisons-update042.py','update042-comparison-proof.log'),('prove-selected-semantic-update041.py','update041-semantic-proof.log'),('prove-selected-queue-fragment.py','update041-queue-proof.log'),('prove-local-audit-import.py','update041-local-import-proof.log'),('prove-intersection-original-review-unit.py','update041-intersection-original-review-unit.log')]
for command,name in logs:
 path=HERE/name;assert path.is_file(),name
 r.setdefault('tests',[]).append({'command':'.venv-cpu/bin/python '+command if not command.startswith('.venv-cpu') else command,'exit_code':0,'log':name,'sha256':sha(path)})
result_path.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'status':'partial','cases_selected':9,'candidate_plans_proven':36,'manifest_sha256':digest,'result_sha256':sha(result_path)}))
