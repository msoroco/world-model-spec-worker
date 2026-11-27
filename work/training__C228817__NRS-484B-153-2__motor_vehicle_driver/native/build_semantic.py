"""Author the exact-law semantic chain for door and passing-traffic cases."""

import copy
import hashlib
import json
from pathlib import Path
from batch_pipeline.store import digest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ASSIGNMENT = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
TEMPLATE = LAW['id'] + '@' + ASSIGNMENT['actor']
PROPOSAL = json.loads((ROOT / 'proposals/cases.json').read_text())


def save(name, value):
    path = ROOT / 'proposals' / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path':'proposals/'+name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {'cell_id':'C228817','actor':'motor_vehicle_driver','status':'draft',
    'relevant_laws':[{'law_id':LAW['id'],'quote':LAW['text'],'applies_to':['motor_vehicle_driver'],
        'relevance_type':'specific_match','confidence':'high',
        'notes':'Frozen load/unload road cell has a driver operating a traffic-side door beside moving traffic.'}],
    'borderline_excluded':[]}
batch_ref=save('relevance_batch.json',relevance)
relevance_ref=save('relevance.json',relevance)
judgments=[
 {'phrase':'closest to passing traffic','note':'Join original road direction and passing trajectory with independently observed door or transfer side.'},
 {'phrase':'open the door of or board or alight','note':'Observe distinct door motion and boarding or alighting; command requests are not physical observations.'},
 {'phrase':'in such a manner as to interfere with moving vehicular traffic','note':'Measure passing vehicle motion, door/person geometry and response ordering; legal interference remains contextual.'}]
template={'template_id':TEMPLATE,'law_id':LAW['id'],'actor':'motor_vehicle_driver',
 'status':'draft','quote':LAW['text'],
 'structure':{'activation':{'description':'Traffic-side door opening, boarding or alighting near moving vehicular traffic',
     'source_clause':'open the door of or board or alight from the side of a vehicle which is closest to passing traffic'},
  'obligation':{'description':'Do not interfere with moving vehicular traffic through that action',
     'source_clause':'in such a manner as to interfere with moving vehicular traffic'},
  'exceptions':[],
  'timing':{'description':'Observe door/person motion before any attributable passing response',
     'source_clause':'in such a manner as to interfere with moving vehicular traffic'},
  'judgment_calls_needed':judgments},
 'parameter_refs':[{'name':'transfer_action','kind':'world_setup','range_or_domain':'board or alight'},
                   {'name':'passing_arrival_frame','kind':'controller','range_or_domain':'110 or 310 frame request; original arrival measured separately'}]}
template_ref=save('template.json',template)
needs=[['st.lane','sig.door_open'],['sig.door_open','ru.occupant_count','ru.pedestrian'],
       ['rel.surface_gap','drv.time_to_conflict','drv.hard_deceleration','kin.velocity']]
observable_refs=[]
for index,(judgment,names) in enumerate(zip(judgments,needs)):
 obs=[{'name':name,'unit':'structured','description':'Original Native actor/frame join and independent four-camera pixel review'} for name in names]
 value={'template_id':TEMPLATE,'phrase':judgment['phrase'],'note':judgment['note'],'status':'draft',
  'observable_requirements':{'observables':copy.deepcopy(obs),'context_inputs':[],
   'sweep_dimensions':[{'name':'passing_arrival_frame','unit':'frame','description':'Requested arrival frame; actual original motion and response measured separately'}],
   'landmarks':[],'recording_needs':copy.deepcopy(obs),
   'limitations':['Door and person commands are not observed motion.','No engineering distance, time or deceleration is a legal interference cutoff.']}}
 observable_refs.append(save(f'judgment_observables_{index}.json',value))
binding={'cell_id':'C228817','actor':'motor_vehicle_driver','status':'draft',
 'established_contexts':[{'name':'roadside_loading_context','source':'Frozen cell; original map and physical source review pending'}],
 'law_refs':[{'template_id':TEMPLATE,'binding_kind':'direct'}],
 'context_refs':[],'fixed_parameters':[],
 'variable_parameters':[{'name':'transfer_action','kind':'world_setup','range_or_domain':'board or alight','used_by_laws':[LAW['id']]},
   {'name':'passing_arrival_frame','kind':'controller','range_or_domain':'110 or 310 frame request','used_by_laws':[LAW['id']]}]}
binding_ref=save('bindings.json',binding)
selected=[case for case in PROPOSAL['cases'] if case.get('target_type') != 'baseline']
for case in selected:
 case['unresolved_judgment_calls']=[j['phrase'] for j in judgments]
 case['deliberate_differences']=['passing_arrival_frame']
 case['variable_assignments']['transfer_action']['kind']='world_setup'
 case['paired_probe_id']=ROOT.name+'__'+case['case_id'].split('__')[-1].split('_')[0]+'_passing_arrival'
 case['probe']={'primary_variable':'passing_arrival_frame',
  'comparison_or_standard':'controlled passing-arrival request; original interference remains unjudged',
  'target_value_or_branch':case['variable_assignments']['passing_arrival_frame']['value']}
baseline=copy.deepcopy(selected[0])
baseline['case_id']=ROOT.name+'__neutral_baseline'
baseline['target_type']='baseline'
baseline['rationale']='Unselected shared road/loading context; no recording or legal outcome'
for key in ('paired_probe_id','deliberate_differences','probe'):
 baseline.pop(key,None)
sweeps=[]
for action, pair in (('board',selected[:2]),('alight',selected[2:])):
 spec={'sweep_id':ROOT.name+'__'+action+'_passing_arrival',
       'target_law_id':LAW['id'],'judgment_refs':copy.deepcopy(judgments),
       'rationale':'Compare controlled passing arrival while door and person action requests stay fixed; no legal threshold inferred.',
       'status':'complete','mode':'one_dimensional',
       'axes':[{'variable':'passing_arrival_frame','observable':'passing_arrival_frame',
          'unit':'frame','min':110,'max':310,'spacing':200,
          'range_rationale':'Two authored passing approach windows aligned with the selected comparison pair.',
          'spacing_rationale':'200 frames separate the selected requests at 20 Hz.',
          'feasibility_evidence':'Four exact Native offline and source-shaped saved checks pass.',
          'measurement':{'method':'Read requested arrival separately from measured original passing trajectory and response',
                         'time_window':'600 original Native frames','statistic':'first'}}],
       'landmarks':[],'variable_assignments':copy.deepcopy(pair[0]['variable_assignments']),
       'recording_description':copy.deepcopy(pair[0]['recording_description'])}
 version=digest(spec);spec['spec_version']=version;spec['planned_case_count']=2
 spec['selection_order']=[case['case_id'] for case in pair]
 for rank,case in enumerate(pair):
  case['sweep_id']=spec['sweep_id'];case['sweep_spec_version']=version
  case['sweep_point']={'passing_arrival_frame':float(case['variable_assignments']['passing_arrival_frame']['value'])}
  case['selection_rank']=rank
 sweeps.append(spec)
PROPOSAL['cases']=selected+[baseline]
PROPOSAL['sweeps_expanded']=True
PROPOSAL['sweep_specs']=sweeps
cases_ref=save('cases.json',PROPOSAL)
index={'format':'worker-semantic-delivery','assignment_id':ROOT.name,
 'stages':{'relevance_batch':batch_ref,'relevance':relevance_ref,'template':template_ref,
           'judgment_observables':observable_refs,'bindings':binding_ref,'cases':cases_ref}}
save('semantic-index.json',index)
print('six-stage exact-law proposal chain authored for four selected cases')
