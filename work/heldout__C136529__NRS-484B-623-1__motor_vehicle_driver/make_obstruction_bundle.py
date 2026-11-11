"""Expand the checked implementation into the physical obstruction exact case."""
import copy
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parent;repo=root.parents[1]
assignment=root.name;branch='slow_for_obstruction';case=assignment+'__'+branch
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest_path=root/'execution-manifest.json';manifest=json.loads(manifest_path.read_text())
primary=manifest['cases'][0]
base=json.loads((root/'construction.json').read_text());base['case_id']=case
for item in base['files']:
    if item['path']=='config.json':
        config=json.loads(item['content']);config['selected_case_id']=case
        config['case_branch']=branch;config['ego_target_mps']=3.0
        config['obstruction_index']=12;config['obstruction_brake_gain']=.4
        config['case']['case_id']=case
        item['content']=json.dumps(config,indent=2)+'\n';item.pop('source',None)
folder=root/'cases'/branch;folder.mkdir(parents=True,exist_ok=True)
path=folder/'construction.json';path.write_text(json.dumps(base,indent=2,ensure_ascii=False)+'\n')
entry=copy.deepcopy(primary);entry['case_id']=case
entry['construction']='cases/'+branch+'/construction.json';entry['construction_sha256']=sha(path)
for k in ('offline','compatibility','negative','post_capture'):entry.pop(k,None)
entry['candidate_risk']={'status':'physical','reason':'A parked vehicle must spawn in the narrow lane and the subject must brake before contact; map spacing and controller dynamics can defeat either.'}
variants=[('fallback1',{'route_step_m':2.5},
           'Native narrow-route selector','number of connected two-direction narrow routes',
           'Primary route sampling finds no valid road; finer waypoint sampling may resolve tessellation.'),
          ('fallback2',{'obstruction_index':13},
           'Native parked-obstruction spawn and bounding-box readback','spawn success and measured overlap with existing geometry',
           'Primary obstruction site is occupied or has invalid body geometry; move the parked actor one waypoint downstream.'),
          ('fallback3',{'obstruction_brake_gain':.3},
           'Original subject/obstruction gap and speed histories','minimum body gap and peak closure speed before stop',
           'Primary braking policy oscillates or approaches closer than the predeclared engineering margin.')]
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
req=plan['requirement_dispositions'][1]
contract=json.loads((root/'first-measurement-contract.json').read_text())
contract['case_id']=case
contract['requirements'][0]['disposition_index']=1
contract['requirements'][0]['requirement']=req['requirement']
contract['requirements'][0]['source']=req['source']
(folder/'measurement-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
spec=json.loads((root/'diagnostic-input.json').read_text())
props=[json.loads(x) for x in spec['files']['prop_state.jsonl'].splitlines()]
for row in props:
    row['obstruction_present']=True
    row['obstruction_geometry']={'actor_id':4,'blueprint_id':'vehicle.tesla.model3',
      'center_xy':[115.0,1.75],
      'vertices_xyz':[[115+dx,1.75+dy,z] for dx in (-2,2) for dy in (-1,1) for z in (0,1)]}
spec['files']['prop_state.jsonl']=''.join(json.dumps(row)+'\n' for row in props)
spec['files']['slow_context.json']=json.dumps({'case_branch':branch,'diagnostic_fixture':True,'native_weather':{'precipitation':0.0,'wetness':0.0},
 'legal_judgment':'unresolved'})+'\n'
spec['files']['fixture-provenance.json']=json.dumps({'kind':'textual CPU diagnostic',
 'case_id':case,'physical_recording':False,'law_or_canonical_acceptance':False})+'\n'
spec_path=folder/'diagnostic-input.json';spec_path.write_text(json.dumps(spec,separators=(',',':'))+'\n')
recipe={'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json',
 'source':str(spec_path.relative_to(repo)),'sha256':sha(spec_path)}],
 'generator':{'source':str(spec_path.relative_to(repo)),'sha256':sha(spec_path)}}
(folder/'diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
proposal_path=root/'proposals/cases.json';proposal=json.loads(proposal_path.read_text())
case_proposal=copy.deepcopy(proposal['cases'][0]);case_proposal['case_id']=case
case_proposal['rationale']='Physical parked-vehicle obstruction with measured reduced subject speed; necessity remains unresolved.'
case_proposal['variable_assignments']['ego_target_mps']['value']=3.0
case_proposal['variable_assignments']['obstruction_present']={'kind':'world_setup','value':True}
case_proposal['paired_probe_id']='safety_obstruction'
case_proposal['deliberate_differences']=['obstruction_present']
proposal['cases'].append(case_proposal);proposal_path.write_text(json.dumps(proposal,indent=2)+'\n')
print(case,entry['construction_sha256'])
