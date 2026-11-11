"""Expand the checked implementation into the physical speed-control exact case."""
import copy
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parent;repo=root.parents[1]
assignment=root.name;branch='slow_under_control';case=assignment+'__'+branch
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest_path=root/'execution-manifest.json';manifest=json.loads(manifest_path.read_text())
primary=manifest['cases'][0]
base=json.loads((root/'construction.json').read_text());base['case_id']=case
for item in base['files']:
    if item['path']=='config.json':
        config=json.loads(item['content']);config['selected_case_id']=case
        config['case_branch']=branch;config['ego_target_mps']=8.0
        config['follower_cruise_mps']=12.0;config['control_search_m']=30.0
        config['case']['case_id']=case
        item['content']=json.dumps(config,indent=2)+'\n';item.pop('source',None)
folder=root/'cases'/branch;folder.mkdir(parents=True,exist_ok=True)
path=folder/'construction.json';path.write_text(json.dumps(base,indent=2,ensure_ascii=False)+'\n')
entry=copy.deepcopy(primary);entry['case_id']=case
entry['construction']='cases/'+branch+'/construction.json';entry['construction_sha256']=sha(path)
for k in ('offline','compatibility','negative','post_capture'):entry.pop(k,None)
entry['candidate_risk']={'status':'physical','reason':'A physical 30 km/h speed-limit sign must exist near the narrow route and govern the subject; map availability, sign coverage and speed tracking may fail.'}
variants=[('fallback1',{'route_step_m':2.5},
           'Native narrow-route selector','number of connected two-direction narrow routes',
           'Primary 5 m route sampling finds no valid narrow road; finer sampling may resolve tessellation.'),
          ('fallback2',{'control_search_m':60.0},
           'Native traffic.speed_limit.30 actor inventory and transforms','nearest physical 30 km/h sign distance to selected route',
           'Primary 30 m search does not find a physical sign; extend the search while preserving sign type and legal source review.'),
          ('fallback3',{'speed_kp':.18,'speed_brake_gain':.25},
           'Original subject speed history under a physical speed-limit sign','peak-to-peak measured speed and sign-governed frames',
           'Primary speed gains oscillate outside a predeclared engineering tracking band under the observed sign.')]
entry['candidates']=[]
for ident,changes,source,metric,condition in variants:
    alt=copy.deepcopy(base);alt['candidate_id']=ident
    for item in alt['files']:
        if item['path']=='config.json':
            cfg=json.loads(item['content']);cfg.update(changes)
            item['content']=json.dumps(cfg,indent=2)+'\n';item.pop('source',None)
    rel='cases/'+branch+'/'+ident+'-construction.json'
    target=root/rel;target.write_text(json.dumps(alt,indent=2,ensure_ascii=False)+'\n')
    entry['candidates'].append({'id':ident,'construction':rel,'construction_sha256':sha(target),
       'trigger':{'source':source,'metric':metric,'failure_condition':condition},
       'changed_knobs':[k+': '+str(config.get(k,5.0 if k=='route_step_m' else None))+' to '+str(v) for k,v in changes.items()]})
entry['measurement_contract']='cases/'+branch+'/measurement-contract.json'
entry['fixture_recipe']='work/'+assignment+'/cases/'+branch+'/diagnostic-recipe.json'
manifest['cases'].append(entry);manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
plan=json.loads((root/'case-plan.json').read_text())
req=plan['requirement_dispositions'][2]
contract=json.loads((root/'first-measurement-contract.json').read_text())
contract['case_id']=case
contract['requirements'][0]['disposition_index']=2
contract['requirements'][0]['requirement']=req['requirement']
contract['requirements'][0]['source']=req['source']
(folder/'measurement-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
spec=json.loads((root/'diagnostic-input.json').read_text())
actors=[json.loads(x) for x in spec['files']['participant_state.jsonl'].splitlines()]
for row in actors:row['ego_speed_mps']=8.0;row['follower_speed_mps']=10.0
spec['files']['participant_state.jsonl']=''.join(json.dumps(row)+'\n' for row in actors)
props=[json.loads(x) for x in spec['files']['prop_state.jsonl'].splitlines()]
for row in props:
    row['control_present']=True
    row['control_geometry']={'actor_id':5,'blueprint_id':'traffic.speed_limit.30',
      'center_xy':[95.0,4.0],
      'vertices_xyz':[[95+dx,4+dy,z] for dx in (-.2,.2) for dy in (-.2,.2) for z in (0,3)]}
spec['files']['prop_state.jsonl']=''.join(json.dumps(row)+'\n' for row in props)
spec['files']['slow_context.json']=json.dumps({'case_branch':branch,'diagnostic_fixture':True,'native_weather':{'precipitation':0.0,'wetness':0.0},
 'legal_judgment':'unresolved',
 'regulatory_source':'synthetic Native traffic.speed_limit.30 fixture; legal authority unresolved'})+'\n'
spec['files']['fixture-provenance.json']=json.dumps({'kind':'textual CPU diagnostic',
 'case_id':case,'physical_recording':False,'law_or_canonical_acceptance':False})+'\n'
spec_path=folder/'diagnostic-input.json';spec_path.write_text(json.dumps(spec,separators=(',',':'))+'\n')
recipe={'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json',
 'source':str(spec_path.relative_to(repo)),'sha256':sha(spec_path)}],
 'generator':{'source':str(spec_path.relative_to(repo)),'sha256':sha(spec_path)}}
(folder/'diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
proposal_path=root/'proposals/cases.json';proposal=json.loads(proposal_path.read_text())
case_proposal=copy.deepcopy(proposal['cases'][0]);case_proposal['case_id']=case
case_proposal['rationale']='Physical 30 km/h sign and reduced subject speed; local regulatory validity and legal outcome remain unresolved.'
case_proposal['variable_assignments']['ego_target_mps']['value']=8.0
case_proposal['variable_assignments']['follower_cruise_mps']['value']=12.0
case_proposal['variable_assignments']['control_present']={'kind':'world_setup','value':True}
case_proposal['paired_probe_id']='lawful_control'
case_proposal['deliberate_differences']=['control_present','ego_target_mps','follower_cruise_mps']
proposal['cases'].append(case_proposal);proposal_path.write_text(json.dumps(proposal,indent=2)+'\n')
print(case,entry['construction_sha256'])
