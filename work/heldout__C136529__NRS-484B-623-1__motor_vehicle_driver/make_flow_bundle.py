"""Expand the checked primary implementation into the flow reference exact case."""
import copy
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parent
repo=root.parents[1]
assignment=root.name
case=assignment+'__flowing_reference'
manifest_path=root/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())
primary=manifest['cases'][0]
base=json.loads((root/'construction.json').read_text())
base['case_id']=case
for item in base['files']:
    if item['path']=='config.json':
        config=json.loads(item['content'])
        config['selected_case_id']=case
        config['case_branch']='flowing_reference'
        config['ego_target_mps']=8.0
        config['case']['case_id']=case
        item['content']=json.dumps(config,indent=2)+'\n'
        item.pop('source',None)
folder=root/'cases/flowing_reference';folder.mkdir(parents=True,exist_ok=True)
construction_path=folder/'construction.json'
construction_path.write_text(json.dumps(base,indent=2,ensure_ascii=False)+'\n')
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
entry=copy.deepcopy(primary)
entry['case_id']=case
entry['construction']='cases/flowing_reference/construction.json'
entry['construction_sha256']=sha(construction_path)
entry.pop('offline',None);entry.pop('compatibility',None);entry.pop('negative',None)
for candidate in entry['candidates']:
    alt=copy.deepcopy(base)
    alt['candidate_id']=candidate['id']
    for item in alt['files']:
        if item['path']=='config.json':
            cfg=json.loads(item['content'])
            changes={'fallback1':{'route_step_m':2.5},'fallback2':{'follower_gain':.3},
                     'fallback3':{'speed_kp':.18,'speed_brake_gain':.25}}[candidate['id']]
            cfg.update(changes)
            item['content']=json.dumps(cfg,indent=2)+'\n'
            item.pop('source',None)
    relative='cases/flowing_reference/'+candidate['id']+'-construction.json'
    path=root/relative;path.write_text(json.dumps(alt,indent=2,ensure_ascii=False)+'\n')
    candidate['construction']=relative;candidate['construction_sha256']=sha(path)
    candidate.pop('offline',None);candidate.pop('compatibility',None)
entry['measurement_contract']='cases/flowing_reference/measurement-contract.json'
entry['fixture_recipe']='work/'+assignment+'/cases/flowing_reference/diagnostic-recipe.json'
entry.pop('post_capture',None)
manifest['cases']=[primary,entry]
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
contract=json.loads((root/'first-measurement-contract.json').read_text())
contract['case_id']=case
(folder/'measurement-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
spec=json.loads((root/'diagnostic-input.json').read_text())
rows=[json.loads(s) for s in spec['files']['participant_state.jsonl'].splitlines()]
for row in rows:row['ego_speed_mps']=8.0;row['follower_speed_mps']=8.0
spec['files']['participant_state.jsonl']=''.join(json.dumps(row)+'\n' for row in rows)
spec['files']['slow_context.json']=json.dumps({'case_branch':'flowing_reference',
 'diagnostic_fixture':True,'native_weather':{'precipitation':0.0,'wetness':0.0},'legal_judgment':'unresolved'})+'\n'
spec['files']['fixture-provenance.json']=json.dumps({'kind':'textual CPU diagnostic',
 'case_id':case,'physical_recording':False,'law_or_canonical_acceptance':False})+'\n'
spec_path=folder/'diagnostic-input.json';spec_path.write_text(json.dumps(spec,separators=(',',':'))+'\n')
recipe={'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json',
 'source':str(spec_path.relative_to(repo)),'sha256':sha(spec_path)}],
 'generator':{'source':str(spec_path.relative_to(repo)),'sha256':sha(spec_path)}}
(folder/'diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
proposal_path=root/'proposals/cases.json';proposal=json.loads(proposal_path.read_text())
case_proposal=copy.deepcopy(proposal['cases'][0])
case_proposal['case_id']=case
case_proposal['rationale']='Measured flow reference on the same narrow road; no legal outcome is assigned.'
case_proposal['variable_assignments']['ego_target_mps']['value']=8.0
proposal['cases'].append(case_proposal)
proposal_path.write_text(json.dumps(proposal,indent=2)+'\n')
print(case,entry['construction_sha256'])
