"""Expand the station software diagnostic into each remaining exact branch."""
import hashlib,json
from pathlib import Path

root=Path(__file__).resolve().parent
repo=root.parents[1]
assignment=root.name
manifest_path=root/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())
primary=json.loads((root/'construction.json').read_text())
base_fixture=json.loads((root/'diagnostic-input.json').read_text())
proposal_path=root/'proposals/cases.json'
proposals=json.loads(proposal_path.read_text())
plan=json.loads((root/'case-plan.json').read_text())
def ref(road,lane,s):return {'road_id':road,'lane_id':lane,'s':s}
variants={
 'front_of_approach':{'route':[ref(7,1,0),ref(7,1,4),ref(7,-1,4)],
    'xs':[-8,-7,-6,-5,-4,-5,-6,-7,-8],'ys':[0]*9,'lane':[7,1]},
 'through_driveway':{'route':[ref(7,1,0),ref(8,2,6),ref(8,2,10),ref(7,-1,8)],
    'xs':[-6,-4,-2,0,0,0,-2,-4,-6],
    'ys':[0,0,0,1,3,1,0,0,0],'lane':[8,2]},
 'remote_reference':{'route':[ref(7,1,30),ref(7,1,40),ref(7,-1,40)],
    'xs':[34,36,38,40,41,40,38,36,34],'ys':[0]*9,'lane':[7,1]}}
for branch,spec in variants.items():
    case_id=assignment+'__'+branch
    folder=root/'cases'/branch;folder.mkdir(parents=True,exist_ok=True)
    construction=json.loads(json.dumps(primary));construction['case_id']=case_id
    for item in construction['files']:
        if item['path']=='config.json':
            config=json.loads(item['content'])
            config['selected_case_id']=case_id
            config['case_branch']=branch
            config['station_survey']['routes'][branch]=spec['route']
            config['case']['case_id']=case_id
            item['content']=json.dumps(config,indent=2)+'\n'
            item.pop('source',None)
    path=folder/'construction.json';path.write_text(json.dumps(construction,indent=2)+'\n')
    fixture=json.loads(json.dumps(base_fixture))
    rows=[json.loads(line) for line in fixture['files']['participant_state.jsonl'].splitlines()]
    for i,row in enumerate(rows):
        x,y=spec['xs'][i],spec['ys'][i]
        ego=row['ego'];ego['center_xy']=[x,y]
        ego['body_vertices_xy']=[[x-1,y-.7],[x+1,y-.7],[x+1,y+.7],[x-1,y+.7]]
        ego['lane_id']=spec['lane'] if (branch!='through_driveway' or 3<=i<=5) else [7,1]
    fixture['files']['participant_state.jsonl']=''.join(json.dumps(r)+'\n' for r in rows)
    provenance=json.loads(fixture['files']['fixture-provenance.json'])
    provenance['case_id']=case_id
    fixture['files']['fixture-provenance.json']=json.dumps(provenance)+'\n'
    fixture_path=folder/'diagnostic-input.json'
    fixture_path.write_text(json.dumps(fixture,separators=(',',':'))+'\n')
    digest=hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    recipe={'format':'worker-fixture-recipe',
      'sources':[{'path':'diagnostic-input.json','source':str(fixture_path.relative_to(repo)),
         'sha256':digest}],
      'generator':{'source':str(fixture_path.relative_to(repo)),'sha256':digest}}
    (folder/'diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    index=1 if branch=='through_driveway' else 0
    disposition=plan['requirement_dispositions'][index]
    contract=json.loads((root/'first-measurement-contract.json').read_text())
    contract['case_id']=case_id
    contract['requirements'][0]['disposition_index']=index
    contract['requirements'][0]['requirement']=disposition['requirement']
    contract['requirements'][0]['source']=disposition['source']
    (folder/'measurement-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    proposal=json.loads(json.dumps(proposals['cases'][0]))
    proposal['case_id']=case_id
    proposal['variable_assignments']['reversal_location']['value']=branch
    proposal['probe']['target_value_or_branch']=branch
    proposal['paired_probe_id']='driveway_use' if branch=='through_driveway' else ('approach_position' if branch=='front_of_approach' else 'entrance_position')
    proposals['cases'].append(proposal)
    manifest['cases'].append({'case_id':case_id,'kind':'delivery',
      'construction':str(path.relative_to(root)),
      'construction_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
      'measurement_procedure':{'entrypoint':'fire_station_finalizer.py'},
      'measurement_contract':str((folder/'measurement-contract.json').relative_to(root)),
      'fixture_recipe':str((folder/'diagnostic-recipe.json').relative_to(repo)),
      'candidate_risk':{'status':'physical','reason':'Station route and body geometry may fail Native capture'},
      'candidates':[],'native_handoff':{'python_env_var':'CARLA_PYTHON',
       'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}})
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
proposal_path.write_text(json.dumps(proposals,indent=2)+'\n')
print([e['case_id'] for e in manifest['cases']])
