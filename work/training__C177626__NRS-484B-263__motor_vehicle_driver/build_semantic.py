"""Write source-grounded draft semantic stage proposals for local review."""
from hashlib import sha256
import json
from pathlib import Path

root=Path(__file__).resolve().parent
assignment=json.loads((Path('inputs')/root.name/'assignment.json').read_text())
plan=json.loads((root/'case-plan.json').read_text())
out=root/'proposals'
out.mkdir(exist_ok=True)
case_ids=[row['case_id'] for row in plan['cases']]
law=assignment['law']
quote=law['text']
recording=json.loads((root/'cases/condition_a/construction.json').read_text())['recording_description']
relevance={'cell_id':assignment['cell_id'],'actor':assignment['actor'],'status':'draft',
           'relevant_laws':[{'law_id':law['id'],'quote':quote,
                             'applies_to':[assignment['actor']],'relevance_type':'specific_match',
                             'confidence':'medium','notes':'Authorized paved access entry is compatible with the fixed enter-road cell; highway designation remains source review.'}],
           'borderline_excluded':[]}
template={'template_id':law['id']+'@'+assignment['actor'],'law_id':law['id'],'actor':assignment['actor'],
          'status':'draft','quote':quote,
          'structure':{'law_id':law['id'],
                       'activation':{'condition':'Driver is about to enter or exit a controlled-access highway; an approaching highway vehicle has proximity constituting an immediate hazard.', 'numeric_conditions':[]},
                       'obligation':{'description':'Yield right-of-way to all such approaching highway vehicles and continue to yield until the driver may proceed with reasonable safety.', 'type':'must', 'numeric_conditions':[]},
                       'exceptions':[],
                       'timing':{'ordering':'Continue yielding until reasonable safety permits proceeding; do not presume all traffic must pass first.'},
                       'judgment_calls_needed':[
                           {'phrase':'controlled-access highway','note':'Public authority and permitted-access status require source review.'},
                           {'phrase':'immediate hazard','note':'Proximity needs independent contextual judgment; projected gap is a diagnostic.'},
                           {'phrase':'reasonable safety','note':'Continuing yield endpoint needs independent contextual judgment.'}]},
          'parameter_refs':[{'name':'engineering_yield_request_gap_s','kind':'controller',
                             'range_or_domain':'2.5 s or 5.0 s diagnostic yield request'},
                            {'name':'observed_approach_and_gap','kind':'subject_behavior',
                             'range_or_domain':'original observed trace or unknown'},
                            {'name':'controlled_access_authority','kind':'world_setup',
                             'range_or_domain':'hash-bound authority source or unresolved'}]}
bindings={'cell_id':assignment['cell_id'],'actor':assignment['actor'],'status':'draft',
          'established_contexts':[],
          'law_refs':[{'template_id':template['template_id'],'binding_kind':'direct'}],
          'context_refs':[],
          'fixed_parameters':[{'name':'entry_access_layout','value':'authored entry ramp and highway junction 100; legal designation unresolved'},
                              {'name':'traffic_inventory','value':['near','far']}],
          'variable_parameters':[{'name':'engineering_yield_request_gap_s','kind':'controller',
                                   'range_or_domain':[5.0,2.5],'used_by_laws':[law['id']]},
                                  {'name':'observed_approach_and_gap','kind':'subject_behavior',
                                   'range_or_domain':'measured or unknown from original 600-frame actor source',
                                   'used_by_laws':[law['id']]},
                                  {'name':'controlled_access_authority','kind':'world_setup',
                                   'range_or_domain':'source-reviewed designation or unresolved',
                                   'used_by_laws':[law['id']]}]}
cases=[{'case_id':root.name+'__baseline','target_law_id':None,'target_type':'baseline',
        'cell_id':assignment['cell_id'],'actor':assignment['actor'],
        'rationale':'Unselected shared authorized-entry geometry and traffic inventory.',
        'variable_assignments':{'engineering_yield_request_gap_s':{'kind':'controller','value':None,'unit':'s'},
                                'observed_approach_and_gap':{'kind':'subject_behavior','value':None,'unit':'structured'},
                                'controlled_access_authority':{'kind':'world_setup','value':None,'unit':'structured'}},
        'recording_description':recording,'unresolved_judgment_calls':['controlled-access designation','immediate hazard','reasonable safety']}]
for index,case in enumerate(case_ids):
    value=5.0 if index==0 else 2.5
    cases.append({'case_id':case,'target_law_id':law['id'],'target_type':'judgment_sweep',
                  'rationale':'Entry case with '+('earlier' if index==0 else 'later')+' engineering yield request; no legal outcome request.',
                  'recording_description':recording,
                  'variable_assignments':{'engineering_yield_request_gap_s':{'kind':'controller','value':value,'unit':'s'},
                                          'observed_approach_and_gap':{'kind':'subject_behavior','value':None,'unit':'structured'},
                                          'controlled_access_authority':{'kind':'world_setup','value':None,'unit':'structured'}},
                  'unresolved_judgment_calls':['controlled-access highway','immediate hazard','reasonable safety'],
                  'cell_id':assignment['cell_id'],'actor':assignment['actor'],
                  'paired_probe_id':'entry_yield_request','deliberate_differences':['engineering_yield_request_gap_s'],
                  'probe':{'primary_variable':'engineering_yield_request_gap_s',
                           'comparison_or_standard':'same entry geometry, traffic placement and camera plan',
                           'target_value_or_branch':value}})
case_stage={'cell_id':assignment['cell_id'],'actor':assignment['actor'],'status':'draft',
            'cases':cases,'sweep_specs':[{'sweep_id':root.name+'__entry_gap_review',
                'target_law_id':law['id'],'status':'incomplete',
                'judgment_refs':template['structure']['judgment_calls_needed'],
                'rationale':'Selected A/B entry pair measures policy and observed gaps while leaving three legal judgments unresolved.',
                'missing_inputs':['Public controlled-access authority source',
                                  'Original Native motion/pixels and independent immediate-hazard and reasonable-safety review']}],
            'sweeps_expanded':True}
for name,obj in [('relevance_batch',relevance),('relevance',relevance),('template',template),
                 ('bindings',bindings),('cases',case_stage)]:
    (out/(name+'.json')).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
judgment_files=[]
for number,call in enumerate(template['structure']['judgment_calls_needed']):
    name=f'judgment_observables_{number}'
    item={'template_id':template['template_id'],'phrase':call['phrase'],
          'note':call['note'],'status':'draft',
          'observable_requirements':{
              'observables':[{'name':'original_entry_and_traffic_history','unit':'structured',
                              'description':'Per-frame original ego and all inventoried approaching highway actor readback.'}],
              'context_inputs':[{'name':'controlled_access_authority','unit':'structured',
                                 'description':'Independent public authority and legally restricted-access source.'}],
              'sweep_dimensions':[],
              'landmarks':[],
              'recording_needs':[{'name':'entry_yield_and_clearance','unit':'structured',
                                  'description':'Original 600-frame access-route, highway actor, gap and camera history.'}],
              'limitations':['Observed gap is not a statutory hazard or reasonable-safety threshold.',
                             'Authority, source pixels and legal judgment require independent review.']}}
    (out/(name+'.json')).write_text(json.dumps(item,indent=2,ensure_ascii=False)+'\n')
    judgment_files.append(name)
index={'format':'worker-semantic-delivery','assignment_id':root.name,
       'stages':{name:{'path':'proposals/'+name+'.json','sha256':sha256((out/(name+'.json')).read_bytes()).hexdigest()}
                 for name in ('relevance_batch','relevance','template','bindings','cases')},
       'judgment_observables':[{'path':'proposals/'+name+'.json',
                                'sha256':sha256((out/(name+'.json')).read_bytes()).hexdigest()}
                               for name in judgment_files]}
(out/'semantic-index.json').write_text(json.dumps(index,indent=2)+'\n')
print(json.dumps({name:row['sha256'] for name,row in index['stages'].items()}))
