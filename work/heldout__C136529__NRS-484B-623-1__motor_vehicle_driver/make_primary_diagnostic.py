"""Construct textual CPU diagnostic sources; never assert a physical recording."""
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parent
repo=root.parents[1]
assignment=root.name
case=assignment+'__slow_with_following_traffic'
config=json.loads((root/'config.json').read_text())
plan=json.loads((root/'case-plan.json').read_text())
source='NRS 484B.623(1) full text in inputs/'+assignment+'/assignment.json'
requirements=[
 ('slow speed and measured following-traffic interaction',('flowing_reference','slow_with_following_traffic')),
 ('reduced speed necessary for safe operation',('slow_for_obstruction',)),
 ('reduced speed in compliance with law',('slow_under_control',))]
plan['requirement_dispositions']=[{'requirement':requirement,'source':source,
 'status':'selected_required','case_ids':[assignment+'__'+name for name in names],
 'evidence_or_gap':'Original participant, prop and context histories are needed; no accepted recording exists.'}
 for requirement,names in requirements]
(root/'case-plan.json').write_text(json.dumps(plan,indent=2,ensure_ascii=False)+'\n')
(root/'first-measurement-contract.json').write_text(json.dumps({
 'format':'worker-measurement-contract','case_id':case,'requirements':[
 {'disposition_index':0,'requirement':requirements[0][0],'source':source,
  'output_key':'slow_speed_observation','method':'measure_slow_branch','value_type':'object',
  'kind':'measured','inputs':['slow_context.json','video_frames.jsonl','trace.jsonl',
                               'participant_state.jsonl','prop_state.jsonl']}],
 'negative':{'remove':['participant_state.jsonl'],
             'error_contains':'Missing required source: participant_state.jsonl'}},indent=2)+'\n')
(root/'proposals').mkdir(exist_ok=True)
proposal={'format':'scenario-coverage-cases','status':'draft','cell_id':'C136529',
 'actor':'motor_vehicle_driver','sweep_specs':[],
 'cases':[{'case_id':case,'target_law_id':'NRS-484B-623-1',
           'target_type':'compliant_attempt',
           'rationale':'Physical slow-speed traffic-interaction sample; no legal outcome is assigned.',
           'variable_assignments':{'ego_target_mps':{'kind':'controller','value':3.0},
                                   'follower_cruise_mps':{'kind':'controller','value':8.0},
                                   'traffic_impedance':{'kind':'subject_behavior','value':None}},
           'unresolved_judgment_calls':['normal and reasonable movement of traffic'],
           'recording_description':config['case']['recording_description'],
           'paired_probe_id':'traffic_impedance',
           'deliberate_differences':['ego_target_mps'],
           'probe':{'primary_variable':'ego_target_mps',
                    'comparison_or_standard':'source-grounded traffic interaction with normal and reasonable movement unresolved',
                    'target_value_or_branch':'slow sample'}}]}
(root/'proposals/cases.json').write_text(json.dumps(proposal,indent=2)+'\n')
example=json.loads((repo/'runtime/fixtures/example.json').read_text())
frames=[json.loads(line) for line in example['files']['video_frames.jsonl'].splitlines() if line.strip()]
trace=[json.loads(line) for line in example['files']['trace.jsonl'].splitlines() if line.strip()]
actors=[];props=[]
for index,(f,t) in enumerate(zip(frames,trace)):
    x,y=t['position_m'][:2]
    actors.append({'frame':f['carla_frame'],'time_s':f['time_s'],
                   'ego_valid':True,'follower_valid':True,'opposing_valid':True,
                   'ego_xy':[x,y],'follower_xy':[x-20+index*.05,y],
                   'opposing_xy':[x+50-index*.2,y-2.75],
                   'ego_speed_mps':3.0,'follower_speed_mps':4.0,
                   'opposing_speed_mps':8.0})
    props.append({'frame':f['carla_frame'],'time_s':f['time_s'],
                  'obstruction_present':False,'obstruction_geometry':None,
                  'control_present':False,'control_geometry':None,
                  'obstruction_visible':None,'control_visible':None})
example['files']['participant_state.jsonl']=''.join(json.dumps(row)+'\n' for row in actors)
example['files']['prop_state.jsonl']=''.join(json.dumps(row)+'\n' for row in props)
example['files']['slow_context.json']=json.dumps({'case_branch':'slow_with_following_traffic',
  'diagnostic_fixture':True,'legal_judgment':'unresolved'})+'\n'
example['files']['fixture-provenance.json']=json.dumps({'kind':'textual CPU diagnostic',
  'case_id':case,'physical_recording':False,'law_or_canonical_acceptance':False})+'\n'
input_path=root/'diagnostic-input.json'
input_path.write_text(json.dumps(example,separators=(',',':'))+'\n')
digest=hashlib.sha256(input_path.read_bytes()).hexdigest()
recipe={'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json',
 'source':str(input_path.relative_to(repo)),'sha256':digest}],
 'generator':{'source':str(input_path.relative_to(repo)),'sha256':digest}}
(root/'diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
manifest_path=root/'execution-manifest.json';manifest=json.loads(manifest_path.read_text())
manifest['cases'][0]['measurement_contract']='first-measurement-contract.json'
manifest['cases'][0]['fixture_recipe']=str((root/'diagnostic-recipe.json').relative_to(repo))
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
print('diagnostic bytes',input_path.stat().st_size)
