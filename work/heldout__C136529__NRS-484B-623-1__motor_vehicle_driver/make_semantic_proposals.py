"""Author the source-grounded semantic stage chain for the exact slow-speed law."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

root=Path(__file__).resolve().parent
repo=root.parents[1]
original=json.loads((repo/'inputs'/root.name/'assignment.json').read_text())
proposals=root/'proposals';proposals.mkdir(exist_ok=True)
law=original['law'];law_id=original['law_id'];actor=original['actor'];cell=original['cell_id']
template_id=law_id+'@'+actor

def write(name,value):
    path=proposals/name;path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    return {'path':'proposals/'+name,'sha256':sha256(path.read_bytes()).hexdigest()}

relevance={'cell_id':cell,'actor':actor,'status':'draft','relevant_laws':[
    {'law_id':law_id,'quote':law['text'],'applies_to':[actor],
     'relevance_type':'specific_match','confidence':'high',
     'notes':'The frozen narrow-road travel cell and following vehicle support a slow-speed interaction; necessity and authority are separate premises.'}],
    'borderline_excluded':[]}
rb=write('relevance_batch.json',relevance);r=write('relevance.json',relevance)
judgments=[
 {'phrase':'normal and reasonable movement of traffic','note':'No statutory numeric traffic-speed, queue-size, or duration cutoff.'},
 {'phrase':'necessary for safe operation','note':'Physical obstruction and reduced speed require source-backed necessity review.'},
 {'phrase':'in compliance with law','note':'Physical speed-limit device does not by itself establish governing legal authority.'}]
template={'template_id':template_id,'law_id':law_id,'actor':actor,'status':'draft','quote':law['text'],
 'structure':{'law_id':law_id,
   'activation':{'condition':'A person drives a motor vehicle at a slow speed that may impede normal and reasonable traffic movement.','numeric_conditions':[]},
   'obligation':{'type':'must_not','description':'Do not drive at a slow speed that impedes normal and reasonable movement of traffic, subject to the stated exceptions.','numeric_conditions':[]},
   'exceptions':[{'trigger':'Reduced speed is necessary for safe operation.','effect':'The slow-speed prohibition has the stated safety exception.','replacement_obligation':'none stated in this section','source_clause':'except when reduced speed is necessary for safe operation'},
                 {'trigger':'Reduced speed is in compliance with law.','effect':'The slow-speed prohibition has the stated compliance exception.','replacement_obligation':'none stated in this section','source_clause':'or in compliance with law'}],
   'timing':{'description':'Observe synchronized subject and following traffic motion over the complete original interval; the statute gives no numeric duration.','numeric_conditions':[]},
   'judgment_calls_needed':judgments},
 'parameter_refs':[
   {'name':'ego_speed_target_mps','kind':'controller','range_or_domain':'nonnegative target m/s; measured speed separate'},
   {'name':'follower_cruise_mps','kind':'controller','range_or_domain':'nonnegative target m/s; measured follower speed separate'},
   {'name':'ego_speed','kind':'subject_behavior','range_or_domain':'measured nonnegative m/s'},
   {'name':'follower_speed','kind':'subject_behavior','range_or_domain':'measured nonnegative m/s'},
   {'name':'follower_gap','kind':'subject_behavior','range_or_domain':'measured nonnegative m'},
   {'name':'obstruction_present','kind':'world_setup','range_or_domain':'source-backed boolean'},
   {'name':'control_present','kind':'world_setup','range_or_domain':'source-backed boolean'},
   {'name':'governing_control_valid','kind':'world_setup','range_or_domain':'separately sourced authority and governed road portion'}]}
t=write('template.json',template)
needs=[
 [('ego_speed_mps','m/s','Measured subject speed in original Native frame joins'),('follower_speed_mps','m/s','Measured following vehicle speed'),('follower_gap_m','m','Measured center separation; full body gap requires source review')],
 [('ego_speed_mps','m/s','Measured subject speed while the physical obstruction is present')],
 [('ego_speed_mps','m/s','Measured subject speed while a sourced governing control is assessed')]]
judgment_refs=[]
for i,(j,recorded) in enumerate(zip(judgments,needs),1):
    listed=[{'name':n,'unit':u,'description':d} for n,u,d in recorded]
    value={'template_id':template_id,'phrase':j['phrase'],'note':j['note'],'status':'draft',
      'observable_requirements':{'observables':deepcopy(listed),'context_inputs':[],
        'sweep_dimensions':[{'name':'ego_speed_target_mps','unit':'m/s','description':'Requested physical speed sample; actual movement measured separately'}],
        'landmarks':[],'recording_needs':deepcopy(listed),
        'limitations':['Original motion and prop/video context cannot set a legal cutoff or establish a legal verdict.']}}
    judgment_refs.append(write(f'judgment_{i}.json',value))
binding={'cell_id':cell,'actor':actor,'status':'draft','established_contexts':['narrow_road layout','travel maneuver','other_vehicle control'],
 'law_refs':[{'template_id':template_id,'binding_kind':'direct'}],'context_refs':[],
 'fixed_parameters':[{'name':'cell_layout','value':'narrow_road','rationale':'Frozen C136529 catalog cell'}],
 'variable_parameters':[{'name':p['name'],'kind':p['kind'],'range_or_domain':p['range_or_domain'],
                         'used_by_laws':[law_id] if p['kind']!='controller' else []}
                        for p in template['parameter_refs']]}
b=write('bindings.json',binding)
# Ordinary exact cases remain the authored construction selections. The initial
# three qualitative sweep plans are explicit and conservative pending range
# calibration; no legal cutoff is supplied by this law or by the diagnostic media.
case_path=proposals/'cases.json';cases=json.loads(case_path.read_text())
existing={c['case_id'].removeprefix(root.name+'__'):c for c in cases['cases'] if c['target_type']!='baseline'}
recording=deepcopy(next(iter(existing.values()))['recording_description'])
values={'flowing_reference':(8.,8.,False,False),
        'slow_with_following_traffic':(3.,8.,False,False),
        'slow_for_obstruction':(3.,8.,True,False),
        'slow_under_control':(8.,12.,False,True),
        'safety_speed_probe__slow_for_obstruction':(6.,8.,True,False),
        'control_speed_probe__slow_under_control':(10.,12.,False,True)}
for branch,c in existing.items():
    ego,following,obstruction,control=values[branch]
    c['target_type']='judgment_sweep'
    c['unresolved_judgment_calls']=[j['phrase'] for j in judgments]
    c['variable_assignments']={
      'ego_speed_target_mps':{'kind':'controller','value':ego},
      'follower_cruise_mps':{'kind':'controller','value':following},
      'ego_speed':{'kind':'subject_behavior','value':None},
      'follower_speed':{'kind':'subject_behavior','value':None},
      'follower_gap':{'kind':'subject_behavior','value':None},
      'obstruction_present':{'kind':'world_setup','value':obstruction},
      'control_present':{'kind':'world_setup','value':control},
      'governing_control_valid':{'kind':'world_setup','value':None}}
    if branch=='flowing_reference': c['paired_probe_id']='traffic_impedance';c['deliberate_differences']=['ego_speed_target_mps']
    elif branch=='slow_with_following_traffic':c['paired_probe_id']='traffic_impedance';c['deliberate_differences']=['ego_speed_target_mps']
    elif branch=='slow_for_obstruction':c['paired_probe_id']='safety_obstruction';c['deliberate_differences']=['obstruction_present']
    elif branch=='slow_under_control':c['paired_probe_id']='lawful_control';c['deliberate_differences']=['control_present','ego_speed_target_mps','follower_cruise_mps']
    elif branch=='safety_speed_probe__slow_for_obstruction':c['paired_probe_id']='safety_speed_response';c['deliberate_differences']=['ego_speed_target_mps']
    else:c['paired_probe_id']='control_speed_response';c['deliberate_differences']=['ego_speed_target_mps']
    c['probe']={'primary_variable':'ego_speed_target_mps' if branch in ('flowing_reference','slow_with_following_traffic','safety_speed_probe__slow_for_obstruction','control_speed_probe__slow_under_control') else ('obstruction_present' if branch=='slow_for_obstruction' else 'control_present'),
                'comparison_or_standard':'physical source coverage; statutory judgment unresolved',
                'target_value_or_branch':branch}
    c['recording_description']=deepcopy(recording)
baseline={'case_id':root.name+'__baseline','target_law_id':None,'target_type':'baseline',
          'rationale':'Shared dry narrow-road reference; no law outcome assigned.',
          'variable_assignments':deepcopy(existing['flowing_reference']['variable_assignments']),
          'recording_description':deepcopy(recording),'unresolved_judgment_calls':[j['phrase'] for j in judgments]}
cases['cases']=[baseline]+[existing[b] for b in ('flowing_reference','slow_with_following_traffic','slow_for_obstruction','slow_under_control','safety_speed_probe__slow_for_obstruction','control_speed_probe__slow_under_control')]
cases['sweep_specs']=[{'sweep_id':f'c136529-judgment-{i}','target_law_id':law_id,
  'judgment_refs':[j],'status':'incomplete',
  'rationale':'Physical coverage planning for an unresolved statutory phrase.',
  'missing_inputs':['A sourced, feasible numeric range and spacing for this physical dimension across the selected narrow-road scenario is not yet documented; the selected cases are fixed exact comparisons, not an asserted full judgment grid.']} for i,j in enumerate(judgments,1)]
cases['sweeps_expanded']=True
c=write('cases.json',cases)
index={'format':'worker-semantic-delivery','assignment_id':root.name,
 'stages':{'relevance_batch':rb,'relevance':r,'template':t,
           'judgment_observables':judgment_refs,'bindings':b,'cases':c}}
write('semantic-index.json',index)
print('authored semantic stages',len(judgment_refs))
