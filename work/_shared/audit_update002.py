"""Check final update002 receipts and preserved legal plans, without Native execution."""
import json,pathlib,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 migration=read(ROOT/'work/_shared/update002-migration.json');runtime=migration['runtime_manifest_sha256'];rows=[]
 for path in sorted((ROOT/'work').glob('*/execution-manifest.json')):
  manifest=read(path);assert manifest['runtime_manifest_sha256']==runtime
  for e in manifest['cases']:
   assert sha(path.parent/e['construction'])==e['construction_sha256']
   assert e['offline']['construction_sha256']==e['construction_sha256']
   compat=read(path.parent/e['compatibility']['receipt'])
   assert compat['passed'] and compat['runtime_manifest_sha256']==runtime and compat['construction_sha256']==e['construction_sha256']
   proofpath=path.parent/e['physical_preparation']['receipt'];proof=read(proofpath)
   assert sha(proofpath)==e['physical_preparation']['sha256']
   assert proof['construction_sha256']==e['construction_sha256'] and proof['runtime_manifest_sha256']==runtime
   assert proof['proof_driver_sha256']==sha(ROOT/'work/_shared/prove_physical002.py')
   for helper,key in [('physical_assessment002.py','fixture_author_sha256'),('native_fixture_sources002.py','native_fixture_author_sha256')]:
    assert proof[key]==sha(ROOT/'work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver'/helper)
   for name,checksum in proof['diagnostic_graph_authors'].items():
    assert checksum==sha(ROOT/'work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver'/('native_'+name+'_fixture002.py'))
   for fixture in proof['fixtures']:
    assert fixture['exit_code']==0 and sha(path.parent/fixture['log'])==fixture['log_sha256'] and sha(path.parent/fixture['result'])==fixture['result_sha256']
    value=read(path.parent/fixture['result']);status={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[fixture['kind']]
    assert value['physical_checks']['maneuver']['status']==status and value['maneuver_completed']==(status=='met')
    assert value['diagnostic_fixture'] is True
   assert proof['lifecycle']['events']==['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started']
   assert e['post_capture']['test_exit_code']==0 and sha(path.parent/e['post_capture']['test_log'])==e['post_capture']['test_log_sha256']
   rows.append({'case_id':e['case_id'],'construction_sha256':e['construction_sha256'],'physical_preparation_sha256':sha(proofpath),'compatibility_sha256':e['compatibility']['sha256'],'passed':True})
 assert len(rows)==236
 out={'format':'worker-update002-final-audit-v1','passed':True,'cases':len(rows),'motion_fixtures':len(rows)*3,'lifecycle_proofs':len(rows),'runtime_manifest_sha256':runtime,'diagnostic_software_only':True,'native_executed':0,'physical_acceptance_claimed':False,'case_proofs':rows}
 (ROOT/'work/_shared/update002-final-audit.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS:236 exact cases,708 motion fixtures,236 ordered lifecycle proofs; Native executed0')
if __name__=='__main__':main()
