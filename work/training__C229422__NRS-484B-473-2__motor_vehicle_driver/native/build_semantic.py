"""Author exact-law parked-lamp semantic stages and two controlled probes."""
import copy
import hashlib
import json
from pathlib import Path
from batch_pipeline.store import digest

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
ASSIGNMENT=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
LAW=ASSIGNMENT['law'];TEMPLATE=LAW['id']+'@'+ASSIGNMENT['actor']
PROPOSAL=json.loads((ROOT/'proposals/cases.json').read_text())


def save(name,value):
    path=ROOT/'proposals'/name;path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    return {'path':'proposals/'+name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


relevance={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'status':'draft',
    'relevant_laws':[{'law_id':LAW['id'],'quote':LAW['text'],'applies_to':[ASSIGNMENT['actor']],
        'relevance_type':'specific_match','confidence':'high',
        'notes':'Frozen highway parking cell requires nighttime and displayed lamp review.'}],
    'borderline_excluded':[]}
batch_ref=save('relevance_batch.json',relevance);relevance_ref=save('relevance.json',relevance)
judgments=[
    {'phrase':'lawfully parked at nighttime upon any highway',
     'note':'Join original highway geometry, parking-rule composition, civil clock and sunset/sunrise sources; sun altitude alone is insufficient.'},
    {'phrase':'such lights shall be depressed or dimmed',
     'note':'Independent four-camera optical review must establish emitted lamp state throughout the interval, separate from CARLA request bits.'},
    {'phrase':'in the event cowl or parking lamps are not used',
     'note':'Review actual cowl or parking lamp use; parking lamp use exercises the disjunctive exception, not a headlamp-intensity cutoff.'}]
template={'template_id':TEMPLATE,'law_id':LAW['id'],'actor':ASSIGNMENT['actor'],'status':'draft','quote':LAW['text'],
 'structure':{'activation':{'description':'Lights displayed on a lawfully parked vehicle at nighttime on a highway',
                            'source_clause':'Whenever lights are displayed upon a vehicle lawfully parked at nighttime upon any highway'},
  'obligation':{'description':'Displayed lights depressed or dimmed when no cowl or parking lamps are used',
                'source_clause':'such lights shall be depressed or dimmed'},
  'exceptions':[{'description':'Cowl or parking lamps are used',
                 'source_clause':'in the event cowl or parking lamps are not used'}],
  'timing':{'description':'Review the entire parked nighttime displayed-light interval',
            'source_clause':'Whenever lights are displayed upon a vehicle lawfully parked at nighttime upon any highway'},
  'judgment_calls_needed':judgments},
 'parameter_refs':[{'name':'headlamp_high','kind':'controller','range_or_domain':'0 low request or 1 high request'},
                   {'name':'parking_on','kind':'controller','range_or_domain':'0 off or 1 position-lamp request'}]}
template_ref=save('template.json',template)
needs=[['drv.standing_or_parked','drv.civil_night','st.highway','env.civil_time'],
       ['sig.headlamp','kin.time'],['sig.position_lamp','sig.headlamp']]
observable_refs=[]
for index,(judgment,names) in enumerate(zip(judgments,needs)):
    obs=[{'name':name,'unit':'structured','description':'Original Native frame join and independent optical/civil/parking review'} for name in names]
    dimensions=[{'name':n,'unit':'index','description':'0/1 CARLA request index, not an observed legal threshold'} for n in ('headlamp_high','parking_on')]
    value={'template_id':TEMPLATE,'phrase':judgment['phrase'],'note':judgment['note'],'status':'draft',
      'observable_requirements':{'observables':copy.deepcopy(obs),'context_inputs':[],
       'sweep_dimensions':dimensions,'landmarks':[],'recording_needs':copy.deepcopy(obs),
       'limitations':['Controller indices are requests only; original optical review controls physical findings.',
                      'Civil nighttime and lawful parking need independent original cited sources.']}}
    observable_refs.append(save(f'judgment_observables_{index}.json',value))
binding={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'status':'draft',
 'established_contexts':[{'name':'highway_parked_lamp_context','source':'Frozen cell plus planned original map, parking and civil-clock source review'}],
 'law_refs':[{'template_id':TEMPLATE,'binding_kind':'direct'}],'context_refs':[],'fixed_parameters':[],
 'variable_parameters':[{'name':n,'kind':'controller','range_or_domain':'0 or 1 request','used_by_laws':[LAW['id']]} for n in ('headlamp_high','parking_on')]}
binding_ref=save('bindings.json',binding)
selected=PROPOSAL['cases']
for case in selected:
    suffix=case['case_id'].split('__')[-1]
    config=json.loads((ROOT/'cases'/suffix/'config.json').read_text())
    case['recording_description']=config['recording_description']
    case['target_type']='judgment_sweep'
    case['unresolved_judgment_calls']=[j['phrase'] for j in judgments]
    high=0 if suffix=='witness_1' else 1
    parking=1 if suffix=='exception_1_2' else 0
    case['variable_assignments']={n:{'kind':'controller','value':v,'unit':'index','source':'selected exact Native config'} for n,v in [('headlamp_high',high),('parking_on',parking)]}
    group='witness' if suffix.startswith('witness') else 'exception'
    axis='headlamp_high' if group=='witness' else 'parking_on'
    case['paired_probe_id']=ROOT.name+'__'+group+'_lamp_request'
    case['deliberate_differences']=[axis]
    case['probe']={'primary_variable':axis,
       'comparison_or_standard':'controlled Native lamp request with common original scene and independent optical review',
       'target_value_or_branch':case['variable_assignments'][axis]['value']}
baseline=copy.deepcopy(selected[0]);baseline['case_id']=ROOT.name+'__neutral_baseline';baseline['target_law_id']=None
baseline['target_type']='baseline';baseline['rationale']='Unselected shared parked highway context without legal outcome'
for key in ('paired_probe_id','deliberate_differences','probe'):baseline.pop(key,None)
sweeps=[]
for group,pair,axis in [('witness',selected[:2],'headlamp_high'),('exception',selected[2:],'parking_on')]:
    spec={'sweep_id':ROOT.name+'__'+group+'_lamp_request','target_law_id':LAW['id'],
      'judgment_refs':copy.deepcopy(judgments),
      'rationale':'Two source-reviewed CARLA request endpoints at fixed nighttime parking context; no legal dimness threshold inferred.',
      'status':'complete','mode':'one_dimensional',
      'axes':[{'variable':axis,'observable':axis,'unit':'index','min':0,'max':1,'spacing':1,
        'range_rationale':'Both supported discrete CARLA request endpoints for this comparison.',
        'spacing_rationale':'One index separates the two distinct request states.',
        'feasibility_evidence':'Four selected Native offline and public source-shaped compatibility checks passed.',
        'measurement':{'method':'Read requested CARLA lamp state separately from independent original optical observation',
                       'time_window':'600 original Native frames','statistic':'first'}}],
      'landmarks':[],'variable_assignments':copy.deepcopy(pair[0]['variable_assignments']),
      'recording_description':copy.deepcopy(pair[0]['recording_description'])}
    version=digest(spec);spec['spec_version']=version;spec['planned_case_count']=2
    spec['selection_order']=[case['case_id'] for case in pair]
    for rank,case in enumerate(pair):
        case['sweep_id']=spec['sweep_id'];case['sweep_spec_version']=version
        case['sweep_point']={axis:float(case['variable_assignments'][axis]['value'])};case['selection_rank']=rank
    sweeps.append(spec)
PROPOSAL['cases']=selected+[baseline];PROPOSAL['sweep_specs']=sweeps;PROPOSAL['sweeps_expanded']=True
cases_ref=save('cases.json',PROPOSAL)
index={'format':'worker-semantic-delivery','assignment_id':ROOT.name,
       'stages':{'relevance_batch':batch_ref,'relevance':relevance_ref,'template':template_ref,
                 'judgment_observables':observable_refs,'bindings':binding_ref,'cases':cases_ref}}
save('semantic-index.json',index)
print('exact parked-lamp semantic stages and four selected sweep cases authored')
