"""Expand the proved signal construction into the other exact branch cases."""
import hashlib
import json
from pathlib import Path

from flashing_yellow import CASES

root=Path(__file__).resolve().parent
repo=root.parents[1]
assignment=root.name
manifest_path=root/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())
primary=json.loads((root/'construction.json').read_text())
base_fixture=json.loads((root/'diagnostic-input.json').read_text())
proposal_path=root/'proposals/cases.json'
proposals=json.loads(proposal_path.read_text())
for branch in ('east_faster_approach','east_clear_approach','west_cautious_approach'):
    case=CASES[branch];case_id=assignment+'__'+branch
    folder=root/'cases'/branch;folder.mkdir(parents=True,exist_ok=True)
    construction=json.loads(json.dumps(primary))
    construction['case_id']=case_id
    for item in construction['files']:
        if item['path']=='config.json':
            config=json.loads(item['content'])
            config['selected_case_id']=case_id
            config['case_branch']=branch
            config['target_speed_mps']=case.approach_target_mps
            config['case']['case_id']=case_id
            if not case.crossing_vehicle:
                config['case']['recording_description']['channels']=[v for v in
                    config['case']['recording_description']['channels'] if v['name']!='crossing_center_xy']
            item['content']=json.dumps(config,indent=2)+'\n'
            item.pop('source',None)
    construction['recording_description']=config['case']['recording_description']
    construction_path=folder/'construction.json'
    construction_path.write_text(json.dumps(construction,indent=2)+'\n')
    construction_hash=hashlib.sha256(construction_path.read_bytes()).hexdigest()
    fixture=json.loads(json.dumps(base_fixture))
    context=json.loads(fixture['files']['signal_context.json'])
    context['selected_direction']=case.direction
    fixture['files']['signal_context.json']=json.dumps(context)+'\n'
    parties=[json.loads(line) for line in fixture['files']['participant_state.jsonl'].splitlines()]
    for row in parties:
        row['ego']['speed_mps']=case.approach_target_mps
        if not case.crossing_vehicle:row['crossing']=None
    fixture['files']['participant_state.jsonl']=''.join(json.dumps(row)+'\n' for row in parties)
    provenance=json.loads(fixture['files']['fixture-provenance.json'])
    provenance['case_id']=case_id
    fixture['files']['fixture-provenance.json']=json.dumps(provenance)+'\n'
    fixture_path=folder/'diagnostic-input.json'
    fixture_path.write_text(json.dumps(fixture,separators=(',',':'))+'\n')
    fixture_hash=hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    recipe={'format':'worker-fixture-recipe',
      'sources':[{'path':'diagnostic-input.json','source':str(fixture_path.relative_to(repo)),
                  'sha256':fixture_hash}],
      'generator':{'source':str(fixture_path.relative_to(repo)),'sha256':fixture_hash}}
    (folder/'diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    contract=json.loads((root/'first-measurement-contract.json').read_text())
    contract['case_id']=case_id
    (folder/'measurement-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    proposal=json.loads(json.dumps(proposals['cases'][0]))
    proposal['case_id']=case_id
    proposal['variable_assignments']['target_speed_mps']['value']=case.approach_target_mps
    proposal['variable_assignments']['crossing_vehicle']['value']=case.crossing_vehicle
    proposal['probe']['target_value_or_branch']=branch
    proposal['recording_description']=config['case']['recording_description']
    proposals['cases'].append(proposal)
    manifest['cases'].append({'case_id':case_id,'kind':'delivery',
      'construction':str(construction_path.relative_to(root)),
      'construction_sha256':construction_hash,
      'measurement_procedure':{'entrypoint':'signal_finalizer.py'},
      'measurement_contract':str((folder/'measurement-contract.json').relative_to(root)),
      'fixture_recipe':str((folder/'diagnostic-recipe.json').relative_to(repo)),
      'candidate_risk':{'status':'physical','reason':'Signal head visibility, governed lane and participant crossing may fail physical capture'},
      'candidates':[],
      'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}})
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
proposal_path.write_text(json.dumps(proposals,indent=2)+'\n')
print([e['case_id'] for e in manifest['cases']])
