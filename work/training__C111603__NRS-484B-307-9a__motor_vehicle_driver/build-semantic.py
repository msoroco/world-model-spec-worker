import hashlib,json
from pathlib import Path
root=Path.cwd();aid='training__C111603__NRS-484B-307-9a__motor_vehicle_driver';p=root/'work'/aid
assignment=json.loads((root/'inputs'/aid/'assignment.json').read_text())
plan=json.loads((p/'case-plan.json').read_text())
text=assignment['law']['text'];law=assignment['law'];actor=assignment['actor'];cell=assignment['cell_id'];law_id=assignment['law_id'];tid=law_id+'@'+actor
recording=json.loads((p/'v2-primary/witness_1/construction.json').read_text())['recording_description']
relevance={'cell_id':cell,'actor':actor,'status':'draft','relevant_laws':[{'law_id':law_id,'quote':text,'applies_to':[actor],'relevance_type':'specific_match','confidence':'high','notes':'Frozen motor vehicle, intersection turn and other-vehicle context match paragraph 9(a). Paragraph 9(b) actor restriction retained separately.'}],'borderline_excluded':[]}
judgments=[
 {'phrase':'pedestrians lawfully within an adjacent crosswalk','note':'Original crosswalk, pedestrian position and lawful status require independent source review.'},
 {'phrase':'other traffic lawfully using the intersection','note':'Other-vehicle physical presence is insufficient to establish lawful use.'},
 {'phrase':'yield the right-of-way','note':'Relative motion and precedence require original sources; no numerical legal cutoff is inferred.'}]
template={'template_id':tid,'law_id':law_id,'actor':actor,'status':'draft','quote':text,'structure':{
 'activation':{'condition':'Motor vehicle faces a steady red with illuminated green turn arrow at an intersection.','numeric_conditions':[]},
 'obligation':{'type':'must','description':'Enter only for the indicated arrow movement and yield to lawfully present adjacent-crosswalk pedestrians and lawfully using intersection traffic.','numeric_conditions':[]},
 'exceptions':[{'trigger':'Paragraph (b) is cited, with eligible operator classes specified in NRS 484B.307(9)(b); frozen motor_vehicle_driver does not establish eligibility.','effect':'Actor eligibility remains source qualified.','replacement_obligation':'No exception-present motor vehicle scenario inferred.','source_clause':'Except as otherwise provided in paragraph (b) [NRS-484B-307-9b]'}],
 'timing':{'description':'Arrow permission while illuminated; movement and yielding at intersection entry and transit.','numeric_conditions':[]},
 'judgment_calls_needed':judgments},'parameter_refs':[]}
observed=[]
for j in judgments:
 observed.append({'template_id':tid,'phrase':j['phrase'],'note':j['note'],'status':'draft',
 'observable_requirements':{'observables':[{'name':'native_actor_signal_samples','unit':'structured','description':'Original frame-joined Native actor and signal states; current CPU samples are synthetic.'}],
 'context_inputs':[],'sweep_dimensions':[],'landmarks':[],
 'recording_needs':[{'name':'native_actor_signal_samples','unit':'structured','description':'Retained original Native state with independent camera/pixel review.'}],
 'limitations':['Physical source values alone do not resolve lawful status, actual arrow pixels or legal yielding.']}})
binding={'cell_id':cell,'actor':actor,'status':'draft',
 'established_contexts':[{'name':'intersection_turn_other_vehicle','source':'frozen C111603 cell and accepted witness proposal'}],
 'law_refs':[{'template_id':tid,'binding_kind':'direct'}],'context_refs':[],
 'fixed_parameters':[],
 'variable_parameters':[{'name':'commanded_turn_path','kind':'controller','range_or_domain':'authored arrow turn or distinct straight movement; actual path measured separately','used_by_laws':[law_id]},
 {'name':'observed_ego_heading','kind':'subject_behavior','range_or_domain':'source-joined Native ego heading; unguaranteed','used_by_laws':[law_id]}]}
base={'commanded_turn_path':{'kind':'controller','value':'right_arrow_turn'},'observed_ego_heading':{'kind':'subject_behavior','value':None}}
canonical={'cell_id':cell,'actor':actor,'status':'draft','sweep_specs':[{'sweep_id':'lawful_presence_and_yield_review','target_law_id':law_id,
 'judgment_refs':judgments,'status':'incomplete','rationale':'Qualitative lawful presence and yielding must stay unresolved pending original source and independent legal review.',
 'missing_inputs':['Original pedestrian/crosswalk and other-vehicle legal context','original arrow pixels and governing direction','original precedence and yielding source review']}],
 'sweeps_expanded':True,'cases':[{'case_id':aid+'__baseline','target_law_id':None,'target_type':'baseline','rationale':'Unselected shared physical context.','variable_assignments':base,'unresolved_judgment_calls':[j['phrase'] for j in judgments],'recording_description':recording}]}
for suffix,movement in [('witness_1','right_arrow_turn'),('witness_2','straight')]:
 canonical['cases'].append({'case_id':aid+'__'+suffix,'target_law_id':law_id,'target_type':'boundary_probe',
 'rationale':'Authored movement contrast under the same red/green-head and other-vehicle fixture; actual arrow direction and yielding remain unknown.',
 'variable_assignments':{'commanded_turn_path':{'kind':'controller','value':movement},'observed_ego_heading':{'kind':'subject_behavior','value':None}},
 'unresolved_judgment_calls':[j['phrase'] for j in judgments],
 'paired_probe_id':aid+'__witness_comparison','deliberate_differences':['commanded_turn_path'],
 'probe':{'primary_variable':'commanded_turn_path','comparison_or_standard':'same signal and other vehicle, different requested movement','target_value_or_branch':movement},
 'recording_description':recording})
def save(name,obj):
 path=p/'proposals'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2)+'\n');return {'path':'proposals/'+name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
refs={'relevance_batch':save('relevance_batch.json',relevance),'relevance':save('relevance.json',relevance),'template':save('template.json',template),
 'judgment_observables':[save('judgment-'+str(i+1)+'.json',j) for i,j in enumerate(observed)],
 'bindings':save('bindings.json',binding),'cases':save('canonical-cases.json',canonical)}
index={'format':'worker-semantic-delivery','assignment_id':aid,'stages':refs}
(p/'proposals/semantic-index.json').write_text(json.dumps(index,indent=2)+'\n')
print('stages',len(refs)+len(observed)-1)
