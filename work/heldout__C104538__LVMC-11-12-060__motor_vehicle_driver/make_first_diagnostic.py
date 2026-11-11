"""Synthetic station sources for first exact software compatibility proof."""
import hashlib,json
from pathlib import Path
from types import SimpleNamespace
from fire_station_geometry import validate_entrance

root=Path(__file__).resolve().parent
repo=root.parents[1]
config=json.loads((root/'config.json').read_text())
case_id=config['selected_case_id']
source=config['station_survey']['station_source']
def wp(x,y,road,lane):
    return SimpleNamespace(road_id=road,lane_id=lane,lane_width=3.0,
        transform=SimpleNamespace(location=SimpleNamespace(x=x,y=y)))
geometry=validate_entrance(wp(-8,0,7,1),wp(0,0,7,1),wp(8,0,7,1),wp(0,6,8,2),source=source)
example=json.loads((repo/'runtime/fixtures/example.json').read_text())
frames=[json.loads(line) for line in example['files']['video_frames.jsonl'].splitlines()]
xs=[-6,-4,-2,-1,0,-1,-2,-4,-6]
parties=[]
for i,fm in enumerate(frames):
    x=xs[i]
    parties.append({'frame':fm['carla_frame'],'time_s':fm['time_s'],'ego':{
      'actor_id':41,'center_xy':[x,0.0],'heading_rad':i*3.141592653589793/8,
      'speed_mps':3.0,'lane_id':[7,1],
      'body_vertices_xy':[[x-1,-.7],[x+1,-.7],[x+1,.7],[x-1,.7]]}})
example['files']['station_context.json']=json.dumps(geometry)+'\n'
example['files']['participant_state.jsonl']=''.join(json.dumps(row)+'\n' for row in parties)
example['files']['fixture-provenance.json']=json.dumps({
  'kind':'textual CPU station diagnostic','case_id':case_id,
  'physical_recording':False,'physical_station':False,
  'law_or_canonical_acceptance':False})+'\n'
path=root/'diagnostic-input.json'
path.write_text(json.dumps(example,separators=(',',':'))+'\n')
digest=hashlib.sha256(path.read_bytes()).hexdigest()
recipe={'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json',
 'source':str(path.relative_to(repo)),'sha256':digest}],
 'generator':{'source':str(path.relative_to(repo)),'sha256':digest}}
(root/'diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
plan=json.loads((root/'case-plan.json').read_text())
disposition=plan['requirement_dispositions'][0]
contract={'format':'worker-measurement-contract','case_id':case_id,
 'requirements':[{'disposition_index':0,'requirement':disposition['requirement'],
   'source':disposition['source'],'output_key':'station_reversal',
   'method':'analyze','value_type':'object','kind':'measured',
   'inputs':['station_context.json','participant_state.jsonl','video_frames.jsonl','trace.jsonl']}],
 'negative':{'remove':['participant_state.jsonl'],
  'error_contains':'Missing required source: participant_state.jsonl'}}
(root/'first-measurement-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
(root/'proposals').mkdir(exist_ok=True)
proposal={'format':'scenario-coverage-cases','status':'draft','cell_id':'C104538',
 'actor':'motor_vehicle_driver','sweep_specs':[],
 'cases':[{'case_id':case_id,'target_law_id':'LVMC-11-12-060',
   'target_type':'judgment_sweep','rationale':'Measure reversal and station-region geometry; no legal conclusion assigned.',
   'variable_assignments':{'reversal_location':{'kind':'environment','value':'front_of_entrance'}},
   'unresolved_judgment_calls':['in front of station entrance','purpose of turning'],
   'recording_description':config['case']['recording_description'],
   'paired_probe_id':'entrance_position','deliberate_differences':['reversal_location'],
   'probe':{'primary_variable':'reversal_location',
      'comparison_or_standard':'surveyed entrance versus remote reference; legal boundary unresolved',
      'target_value_or_branch':'front of entrance'}}]}
(root/'proposals/cases.json').write_text(json.dumps(proposal,indent=2)+'\n')
manifest_path=root/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())
entry=manifest['cases'][0]
entry['measurement_contract']='first-measurement-contract.json'
entry['fixture_recipe']=str((root/'diagnostic-recipe.json').relative_to(repo))
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
print(path.stat().st_size)
