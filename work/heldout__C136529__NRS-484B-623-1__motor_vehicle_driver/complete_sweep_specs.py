"""Freeze three fixed physical speed grids without making a legal cutoff."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
root=Path(__file__).resolve().parent
repo=root.parents[1]
sys.path.insert(0,str(repo/'runtime/scenario_pipeline'))
from batch_pipeline.store import digest
p=root/'proposals'
read=lambda name:json.loads((p/name).read_text())
def write(name,value):
    path=p/name;path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    return sha256(path.read_bytes()).hexdigest()
index=read('semantic-index.json');template=read('template.json');binding=read('bindings.json');cases=read('cases.json')
# The observed ego speed is the measured source channel; the separate
# controller setpoint is the varied physical input.
for item in template['parameter_refs']:
    if item['name']=='ego_speed':item['name']='ego_speed_mps'
for item in binding['variable_parameters']:
    if item['name']=='ego_speed':item['name']='ego_speed_mps'
for case in cases['cases']:
    assignment=case['variable_assignments']
    if 'ego_speed' in assignment:assignment['ego_speed_mps']=assignment.pop('ego_speed')
for i in range(1,4):
    name=f'judgment_{i}.json';observation=read(name)
    observation['observable_requirements']['sweep_dimensions']=[{
      'name':'ego_speed_mps','unit':'m/s',
      'description':'Original measured subject speed across fixed requested-speed samples; no legal threshold.'}]
    index['stages']['judgment_observables'][i-1]['sha256']=write(name,observation)
index['stages']['template']['sha256']=write('template.json',template)
index['stages']['bindings']['sha256']=write('bindings.json',binding)
by_suffix={case['case_id'].removeprefix(root.name+'__'):case for case in cases['cases']}
grids=[
 ('c136529-traffic-speed-grid','normal and reasonable movement of traffic',3.0,8.0,
  ['slow_with_following_traffic','flowing_reference'],
  'Sample subject speed with no physical obstruction or control and the same following-traffic controller.'),
 ('c136529-safety-speed-grid','necessary for safe operation',3.0,6.0,
  ['slow_for_obstruction','safety_speed_probe__slow_for_obstruction'],
  'Sample subject speed with the same physical parked-vehicle obstruction and following-traffic controller.'),
 ('c136529-control-speed-grid','in compliance with law',8.0,10.0,
  ['slow_under_control','control_speed_probe__slow_under_control'],
  'Sample subject speed with the same physical Native speed-limit sign and follower controller; governing authority is separately unresolved.')]
selected=[]
for sweep_id,phrase,low,high,suffixes,rationale in grids:
    ref=next(j for j in template['structure']['judgment_calls_needed'] if j['phrase']==phrase)
    first=by_suffix[suffixes[0]]
    axis={'variable':'ego_speed_target_mps','observable':'ego_speed_mps','unit':'m/s',
          'min':low,'max':high,'spacing':high-low,
          'measurement':{'method':'original synchronized 20 Hz Native participant positions and velocity',
                         'time_window':'all original frames','statistic':'mean'},
          'range_rationale':rationale+' Endpoints are engineering samples, not statutory bounds.',
          'spacing_rationale':'Two fixed endpoints isolate the physical speed response while holding the branch condition fixed; all intermediate judgments remain unresolved.',
          'feasibility_evidence':'Exact runner/controller, route construction, source camera capture, and saved-source CPU compatibility passed for both requested endpoints; actual Native motion is pending.'}
    spec={'sweep_id':sweep_id,'target_law_id':template['law_id'],'judgment_refs':[ref],
          'status':'complete','mode':'one_dimensional','axes':[axis],'landmarks':[],
          'rationale':rationale,'variable_assignments':deepcopy(first['variable_assignments']),
          'recording_description':deepcopy(first['recording_description'])}
    version=digest(spec)
    spec.update(spec_version=version,planned_case_count=2,
                selection_order=[by_suffix[s]['case_id'] for s in suffixes])
    selected.append(spec)
    for rank,(suffix,value) in enumerate(zip(suffixes,(low,high))):
        case=by_suffix[suffix]
        case['sweep_id']=sweep_id;case['sweep_spec_version']=version
        case['sweep_point']={'ego_speed_target_mps':value}
        case['selection_rank']=rank
        case['sweep_measurements']=[{'observable':'ego_speed_mps','unit':'m/s',
                                    'measurement':deepcopy(axis['measurement'])}]
        case['deliberate_differences']=['ego_speed_target_mps']
        case['unresolved_judgment_calls']=[j['phrase'] for j in template['structure']['judgment_calls_needed']]
        if case['variable_assignments']['ego_speed_target_mps']['value']!=value:
            raise ValueError('Selected exact case setpoint differs from fixed sweep point')
cases['sweep_specs']=selected
cases['sweeps_expanded']=True
order=['baseline','slow_with_following_traffic','flowing_reference',
       'slow_for_obstruction','safety_speed_probe__slow_for_obstruction',
       'slow_under_control','control_speed_probe__slow_under_control']
cases['cases']=[by_suffix[suffix] for suffix in order]
index['stages']['cases']['sha256']=write('cases.json',cases)
write('semantic-index.json',index)
print('froze',len(selected),'physical grids over',sum(s['planned_case_count'] for s in selected),'exact cases')
