"""Freeze two three-point engineering grids; no legal thresholds or labels."""
import json,hashlib,sys
from pathlib import Path
r=Path(__file__).resolve().parent;p=r/'proposals';repo=r.parents[1]
sys.path.insert(0,str(repo/'runtime/scenario_pipeline'))
from batch_pipeline.sweeps import expand_sweeps

def read(name):return json.loads((p/(name+'.json')).read_text())
def write(name,value):(p/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
lid='NRS-484B-113-1'
template=read('template');bindings=read('bindings');cases=read('cases');observed=read('judgment_interference')
new={'name':'other_traffic_brake_start_frame','kind':'world_setup','range_or_domain':'brake onset frame in a fixed 160-frame capture','used_by_laws':[lid]}
if new['name'] not in [x['name'] for x in template['parameter_refs']]:template['parameter_refs'].append({k:v for k,v in new.items() if k!='used_by_laws'})
if new['name'] not in [x['name'] for x in bindings['variable_parameters']]:bindings['variable_parameters'].append(new)
req=observed['observable_requirements'];req['sweep_dimensions']=[{'name':'other_traffic_brake_start_frame','unit':'frame','description':'Authored onset of other-traffic braking within one frozen capture.'}]
for case in cases['cases']:
 if new['name'] not in case['variable_assignments']:case['variable_assignments'][new['name']]={'kind':'world_setup','value':80}
# The parent of each grid is an engineering controller or world setup, not a law cutoff.
base=cases['cases'][1]['recording_description'];brakes=cases['cases'][3]['recording_description']
axes=[
 (r.name+'__backing_safety_spacing_grid',[{'phrase':'reasonable safety','note':'No statutory numeric safety cutoff.'}], 'other_traffic_spacing','m',8,16,4,'minimum original actor-center distance over the backing interval','The 8–16 m commanded spawn range spans visible close and clear encounter geometry; 4 m spacing resolves an interior physical setting.',base),
 (r.name+'__backing_interference_onset_grid',[{'phrase':'without interfering with other traffic','note':'Traffic interference requires independent original-source observations.'}], 'other_traffic_brake_start_frame','frame',40,120,40,'other vehicle original speed change over the backing interval','Frames 40–120 bracket early and late braking within 160 captured frames; 40-frame spacing gives an interior onset.',brakes)]
specs=[]
for sid,refs,var,unit,low,high,step,method,rationale,description in axes:
 specs.append({'sweep_id':sid,'target_law_id':lid,'judgment_refs':refs,'status':'complete','mode':'one_dimensional','axes':[{'variable':var,'observable':var,'unit':unit,'min':low,'max':high,'spacing':step,'measurement':{'method':method,'time_window':'all original backing frames','statistic':'min' if unit=='m' else 'first'},'range_rationale':rationale,'spacing_rationale':'Three fixed physical settings including both endpoints and one interior point; no legal cutoff.','feasibility_evidence':'Native waypoint selection and timed control are encoded in the exact runner; actual realization requires retained original source review.'}], 'landmarks':[],'rationale':'Fixed three-point physical coverage; legal judgment remains unresolved.','variable_assignments':{'reverse_motion':{'kind':'subject_behavior','value':None},'other_traffic_spacing':{'kind':'world_setup','value':12.0},'other_traffic_speed_policy':{'kind':'world_setup','value':'braking' if unit=='frame' else 'steady'},'other_traffic_brake_start_frame':{'kind':'world_setup','value':80}},'recording_description':description})
cases['cases']=cases['cases'][:4];cases['sweep_specs']=specs;cases.pop('sweeps_expanded',None)
expand_sweeps(cases,[template],bindings)
write('template',template);write('bindings',bindings);write('judgment_interference',observed);write('cases',cases)
index=read('semantic-index')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
for stage,reference in index['stages'].items():
 for ref in reference if isinstance(reference,list) else [reference]:ref['sha256']=sha(r/ref['path'])
write('semantic-index',index)
print('expanded',len(cases['cases']),'canonical cases including baseline;',sum(len(s['selection_order']) for s in specs),'fixed-grid points')
