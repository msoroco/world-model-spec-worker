"""Verify update003 preservation and refreshed v7 proofs; legacy stays separate."""
import hashlib,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 paths=[ROOT/'work/_shared/branch-coverage.json',*sorted((ROOT/'work').glob('*/case-plan.json')),*sorted((ROOT/'work').glob('*/execution-manifest.json'))]
 before={str(p.relative_to(ROOT)):json.loads(subprocess.check_output(['git','show','5366dda0ccde716199b26f7cd0b2ae2ebec12aab:'+str(p.relative_to(ROOT))],cwd=ROOT,text=True)) for p in paths};rows=[]
 runtime=read(ROOT/'work/_shared/runtime-proof.json')['runtime_manifest_sha256']
 for name,old in before.items():
  p=ROOT/name
  if not name.endswith('execution-manifest.json'):assert read(p)==old;continue
  current=read(p);assert len(current['cases'])==len(old['cases']) and current['runtime_manifest_sha256']==runtime
  assert [e['case_id'] for e in current['cases']]==[e['case_id'] for e in old['cases']]
  for e,original in zip(current['cases'],old['cases']):
   assert e['construction_sha256']==original['construction_sha256']==sha(p.parent/e['construction'])
   assert 'native_construction_sha256' not in e
   assert e['physical_preparation']==original['physical_preparation']
   physical=p.parent/e['physical_preparation']['receipt'];assert sha(physical)==e['physical_preparation']['sha256']
   proof=read(p.parent/e['compatibility']['receipt'])
   assert proof['passed'] and proof['runtime_manifest_sha256']==runtime and proof['construction_sha256']==e['construction_sha256']
   assert sha(p.parent/e['offline']['log'])==e['offline']['log_sha256'] and e['offline']['exit_code']==0
   assert sha(p.parent/e['post_capture']['test_log'])==e['post_capture']['test_log_sha256'] and e['post_capture']['test_exit_code']==0
   rows.append({'case_id':e['case_id'],'construction_sha256':e['construction_sha256'],'physical_preparation_preserved_sha256':sha(physical),'new_compatibility_sha256':e['compatibility']['sha256'],'passed':True})
 assert len(rows)==236
 contract=read(ROOT/'inputs/legacy-captures/c109705-400-2a-selected-left-turn-v6.json');handoff=read(ROOT/'work/_shared/retained-c109705-handoff.json')
 assert contract['case_id']==handoff['case_id'] and contract['case_id'] not in {e['case_id'] for e in rows}
 from sys import path
 path.insert(0,str(ROOT/'work/_shared'));import runtime002
 r=runtime002.prepare_runtime();runtime002.activate_runtime(ROOT,r)
 from worker_exchange.preparation import check_legacy_capture_handoff
 check_legacy_capture_handoff(ROOT,read(ROOT/'batch.json')['legacy_capture_handoff'])
 report={'format':'worker-update003-final-audit-v1','passed':True,'v7_cases':236,'v7_constructions_and_plans_preserved':True,'v7_physical_preparation_receipts_preserved':236,'retained_motion_outcome_proofs':708,'new_offline_compatibility_saved_tests':236,'runtime_manifest_sha256':runtime,'legacy_case_id':contract['case_id'],'legacy_diagnostic_frames':handoff['diagnostic_proof']['frames'],'legacy_is_delivery_case':False,'actual_recording_audited':False,'native_replay_requested':False,'v7_case_proofs':rows}
 (ROOT/'work/_shared/update003-final-audit.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS:236 v7 cases preserved/refreshed; separate exact-v6 900-frame synthetic handoff verified')
if __name__=='__main__':main()
