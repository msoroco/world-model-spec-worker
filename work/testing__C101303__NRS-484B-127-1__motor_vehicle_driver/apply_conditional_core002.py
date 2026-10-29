"""Correct only conditional Core projection declarations; retain statutory sources."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def write(path,data):path.write_text(json.dumps(data,indent=2)+'\n')
def main():
 targets=[p for p in sorted((ROOT/'work').glob('*/execution-manifest.json')) if 'NRS-484B-413-2' in p.parent.name or p.parent.name=='testing__C376646__NRS-484B-250-4__motor_vehicle_driver']
 changes=[];counts={};preserved={}
 for path in targets:
  manifest=read(path);folder=path.parent;before_plan=sha(folder/'case-plan.json')
  for entry in manifest['cases']:
   source=folder/entry['construction'];bundle=read(source);config_item=next(f for f in bundle['files'] if f['path']=='config.json');cfg=json.loads(config_item['content'])
   removed=['sig.turn_indicator'] if cfg['law_id']=='NRS-484B-413-2' else ['dev.traffic_signal','dev.governs']
   if cfg['law_id']=='NRS-484B-250-4' and cfg.get('installed_heads') is not False:raise ValueError('Only actually no-installed-head contexts may use this correction')
   original=list(cfg['required_atoms']);missing=set(removed)-set(original)
   if missing:raise ValueError('Conditional declaration already changed; review before rerunning '+entry['case_id'])
   contract=folder/entry['measurement_contract'];contract_sha=sha(contract);old_construction=sha(source)
   cfg['required_atoms']=[a for a in original if a not in removed]
   cfg_path=ROOT/config_item['source'] if config_item.get('source') else source.parent/'config.json'
   write(cfg_path,cfg);config_item['content']=cfg_path.read_text();write(source,bundle)
   entry['construction_sha256']=sha(source)
   analysis=next(f['content'] for f in bundle['files'] if f['path']==entry['measurement_procedure']['entrypoint'])
   entry['measurement_procedure']['analysis_revision']=hashlib.sha256(analysis.encode()).hexdigest()
   # Historical receipt files remain intact; their stale declarations cannot qualify a changed construction.
   for key in ('offline','compatibility','negative','physical_preparation','post_capture'):entry.pop(key,None)
   if sha(contract)!=contract_sha:raise AssertionError('Statutory measurement contract changed')
   changes.append({'case_id':entry['case_id'],'assignment_id':folder.name,'removed_required_core_atoms':removed,'required_atoms_before':original,'required_atoms_after':cfg['required_atoms'],'old_construction_sha256':old_construction,'construction_sha256':entry['construction_sha256'],'analysis_revision':entry['measurement_procedure']['analysis_revision'],'config_sha256':sha(cfg_path),'law_contract':str(contract.relative_to(ROOT)),'law_contract_sha256':contract_sha,'law_contract_unchanged':True,'controller_scene_and_raw_acquisition_unchanged':True})
   counts[cfg['law_id']]=counts.get(cfg['law_id'],0)+1
  write(path,manifest)
  if sha(folder/'case-plan.json')!=before_plan:raise AssertionError('Preserved case plan changed')
  preserved[str((folder/'case-plan.json').relative_to(ROOT))]=before_plan
 if counts!={'NRS-484B-413-2':20,'NRS-484B-250-4':2}:raise AssertionError(counts)
 report={'format':'worker-conditional-core-declaration-correction-v002','cases':22,'counts':counts,'changes':changes,'preserved_case_plan_hashes':preserved,'rationale':{'NRS-484B-250-4':'The two C376646 no-installed-signal qualification contexts have no signal entity/governance domain. Raw head count and every-frame empty head state inventory remain mandatory source-bound measurements; unsupported positive Core presence/governance assertions are removed, not the statutory activation test. No trusted global Core absence receipt is fabricated.','NRS-484B-413-2':'Pinned Core TurnSide represents left/right but not observed off/hazard. Full startup/approach/interruption histories legitimately contain off frames. Raw source-bound on/off and traveled-distance continuity measurements remain mandatory; optional actual Core directions remain untouched.'},'raw_law_sources_retained':['signal_context.json','interaction_history.jsonl','signal_history.jsonl','case_observation.json','original camera photometry and frame identities'],'law_requirements_or_measurement_contracts_removed':False,'core_entities_or_values_fabricated':False,'revalidation_required':True,'physical_acceptance_claimed':False}
 out=ROOT/'work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver/conditional-core002-review.json';write(out,report)
 print('Corrected22 conditional Core declarations; plans/contracts/raw sources retained; exact proofs invalidated for revalidation.')
if __name__=='__main__':main()
