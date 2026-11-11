"""Author canonical draft stage proposals for the exact flashing-yellow law."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

root=Path(__file__).resolve().parent
repo=root.parents[1]
assignment=json.loads((repo/'inputs'/root.name/'assignment.json').read_text())
proposal=root/'proposals';proposal.mkdir(exist_ok=True)
law=assignment['law'];law_id=assignment['law_id'];actor=assignment['actor'];cell=assignment['cell_id']
template_id=law_id+'@'+actor
def write(name,value):
    path=proposal/name;path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    return {'path':'proposals/'+name,'sha256':sha256(path.read_bytes()).hexdigest()}

relevance={'cell_id':cell,'actor':actor,'status':'draft',
 'relevant_laws':[{'law_id':law_id,'quote':law['text'],'applies_to':[actor],
    'relevance_type':'specific_match','confidence':'high',
    'notes':'The frozen intersection/through-lane signal cell supports measured yellow-lens passage; actual official status and caution remain open.'}],
 'borderline_excluded':[]}
rb=write('relevance_batch.json',relevance);r=write('relevance.json',relevance)
judgments=[
 {'phrase':'rapidly flashing','note':'The law supplies no numerical flash frequency; 2 Hz is a source-capture engineering setting.'},
 {'phrase':'illuminated yellow lens used with an official traffic-control device','note':'Native Yellow/Off state does not prove lens pixels or official authority.'},
 {'phrase':'with caution','note':'Measured motion and crossing context do not set a legal caution cutoff.'}]
parameters=[
 {'name':'target_speed_mps','kind':'controller','range_or_domain':'positive engineering approach speed in m/s'},
 {'name':'flash_period_s','kind':'controller','range_or_domain':'positive engineering period in seconds'},
 {'name':'crossing_vehicle','kind':'world_setup','range_or_domain':'present or absent'},
 {'name':'approach_direction','kind':'world_setup','range_or_domain':'east or west governed lane'},
 {'name':'native_yellow_transitions','kind':'subject_behavior','range_or_domain':'nonnegative observed Native transition count'},
 {'name':'ego_speed_mps','kind':'subject_behavior','range_or_domain':'nonnegative measured m/s'},
 {'name':'official_control_valid','kind':'world_setup','range_or_domain':'source-backed unresolved authority'}]
template={'template_id':template_id,'law_id':law_id,'actor':actor,'status':'draft',
 'quote':law['text'],'structure':{'law_id':law_id,
   'activation':{'condition':'A rapidly flashing illuminated yellow lens is used with an official traffic-control device at an intersection or other hazardous location.','numeric_conditions':[]},
   'obligation':{'type':'conditional_permission','description':'A driver may pass the light and traverse the intersection or other hazardous location only with caution.','numeric_conditions':[]},
   'exceptions':[],
   'timing':{'description':'Observe original-frame lamp state and driver approach and traversal throughout the hazardous location.','numeric_conditions':[]},
   'judgment_calls_needed':judgments},'parameter_refs':parameters}
t=write('template.json',template)
needs=[
 [('native_yellow_on','boolean','Original Native Yellow/Off readback, with separate pixel review')],
 [('native_yellow_on','boolean','Native readback; original lens pixels require independent source-camera review')],
 [('ego_speed_mps','m/s','Measured approach speed; crossing traffic remains in original participant source when present')]]
judgment_refs=[]
for i,(judgment,observed) in enumerate(zip(judgments,needs),1):
    listed=[{'name':n,'unit':u,'description':d} for n,u,d in observed]
    value={'template_id':template_id,'phrase':judgment['phrase'],'note':judgment['note'],
       'status':'draft','observable_requirements':{'observables':deepcopy(listed),
       'context_inputs':[],'sweep_dimensions':[{'name':'target_speed_mps','unit':'m/s',
         'description':'Engineering approach-speed samples; actual motion measured separately'}],
       'landmarks':[],'recording_needs':deepcopy(listed),
       'limitations':['Original Native state is not a legal cutoff or proof of visual lens illumination, authority or caution.']}}
    judgment_refs.append(write(f'judgment_{i}.json',value))
binding={'cell_id':cell,'actor':actor,'status':'draft',
 'established_contexts':['intersection layout','through movement','traffic signal control'],
 'law_refs':[{'template_id':template_id,'binding_kind':'direct'}],'context_refs':[],
 'fixed_parameters':[{'name':'cell_layout','value':'intersection',
   'rationale':'Frozen C111273 catalog cell'}],
 'variable_parameters':[{'name':p['name'],'kind':p['kind'],
   'range_or_domain':p['range_or_domain'],
   'used_by_laws':[law_id] if p['kind']!='controller' else []} for p in parameters]}
b=write('bindings.json',binding)
cases=json.loads((proposal/'cases.json').read_text())
by_branch={item['case_id'].removeprefix(root.name+'__'):item for item in cases['cases']
           if item['target_type']!='baseline'}
manifest=json.loads((root/'execution-manifest.json').read_text())
descriptions={entry['case_id'].removeprefix(root.name+'__'):
    json.loads((root/entry['construction']).read_text())['recording_description']
    for entry in manifest['cases']}
from flashing_yellow import CASES
for branch,item in by_branch.items():
    item['recording_description']=deepcopy(descriptions[branch])
    physical=CASES[branch]
    item['target_type']='judgment_sweep'
    item['unresolved_judgment_calls']=[j['phrase'] for j in judgments]
    item['variable_assignments']={
      'target_speed_mps':{'kind':'controller','value':physical.approach_target_mps},
      'flash_period_s':{'kind':'controller','value':.5},
      'crossing_vehicle':{'kind':'world_setup','value':physical.crossing_vehicle},
      'approach_direction':{'kind':'world_setup','value':physical.direction},
      'native_yellow_transitions':{'kind':'subject_behavior','value':None},
      'ego_speed_mps':{'kind':'subject_behavior','value':None},
      'official_control_valid':{'kind':'world_setup','value':None}}
    item['paired_probe_id']=('approach_speed_sample' if branch in ('east_cautious_approach','east_faster_approach')
         else 'crossing_traffic_context' if branch=='east_clear_approach' else 'approach_direction')
    item['deliberate_differences']=[('target_speed_mps' if branch=='east_faster_approach' else
       'crossing_vehicle' if branch=='east_clear_approach' else 'approach_direction')]
    item['probe']={'primary_variable':item['deliberate_differences'][0],
      'comparison_or_standard':'controlled original-source comparison; legal caution unresolved',
      'target_value_or_branch':branch}
baseline={'case_id':root.name+'__baseline','target_law_id':None,'target_type':'baseline',
 'rationale':'Same governed intersection reference; no legal result assigned.',
 'variable_assignments':deepcopy(by_branch['east_cautious_approach']['variable_assignments']),
 'recording_description':deepcopy(by_branch['east_cautious_approach']['recording_description']),
 'unresolved_judgment_calls':[j['phrase'] for j in judgments]}
cases['cases']=[baseline]+[by_branch[name] for name in CASES]
cases['sweep_specs']=[{'sweep_id':f'c111273-judgment-{i}',
    'target_law_id':law_id,'judgment_refs':[j], 'status':'incomplete',
    'rationale':'Physical source coverage for an unresolved statutory phrase.',
    'missing_inputs':['A sourced numeric range and spacing for this judgment dimension is not supplied by the statute; the selected cases are exact engineering comparisons.']}
    for i,j in enumerate(judgments,1)]
cases['sweeps_expanded']=True
c=write('cases.json',cases)
index={'format':'worker-semantic-delivery','assignment_id':root.name,
 'stages':{'relevance_batch':rb,'relevance':r,'template':t,
           'judgment_observables':judgment_refs,'bindings':b,'cases':c}}
write('semantic-index.json',index)
print('authored semantic stages',len(judgment_refs))
