"""Author source-faithful canonical semantic proposals for adjacent path use."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
LAW='LVMC-11-40-120'
ACTOR='cycle_or_scooter_operator'
TEXT='Whenever a usable path for bicycles, electric bicycles, or electric scooters has been provided adjacent to a roadway, riders of bicycles, electric bicycles, and electric scooters shall use such path and shall not use the roadway.'
TID=LAW+'@'+ACTOR
REC=json.loads((HERE/'config.json').read_text())['recording_description']
J={'phrase':'usable path','note':'Path usability requires reviewed surface, continuity and obstruction sources; no automatic legal predicate.'}


def write(name,obj):
    path=HERE/'proposals'/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
    return {'path':str(path.relative_to(HERE)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance={'cell_id':'C230224','actor':ACTOR,'status':'draft',
        'relevant_laws':[{'law_id':LAW,'quote':TEXT,'applies_to':[ACTOR],
            'relevance_type':'direct','confidence':'high',
            'notes':'Frozen cycle-path travel case; actual path usability, device identity and occupancy require original sources.'}],
        'borderline_excluded':[]}
    refs={'relevance_batch':write('relevance-batch.json',relevance),
          'relevance':write('relevance.json',relevance)}
    template={'template_id':TID,'law_id':LAW,'actor':ACTOR,'quote':TEXT,'status':'draft',
        'structure':{'law_id':LAW,
          'activation':{'condition':'A usable bicycle/electric bicycle/electric scooter path is provided adjacent to a roadway.','numeric_conditions':[]},
          'obligation':{'type':'must','description':'A rider uses that path and does not use the roadway.','numeric_conditions':[]},
          'exceptions':[],
          'timing':{'description':'Continuous while riding beside the usable adjacent path.','numeric_conditions':[]},
          'judgment_calls_needed':[J]},
        'parameter_refs':[{'name':'path_usable_context','kind':'world_setup','range_or_domain':'source-reviewed usable adjacent path condition'},
                          {'name':'observed_occupancy','kind':'subject_behavior','range_or_domain':'Native footprint occupancy on path and roadway'},
                          {'name':'commanded_path_choice','kind':'controller','range_or_domain':['path','roadway']}]}
    refs['template']=write('template.json',template)
    observable={'template_id':TID,'phrase':J['phrase'],'note':J['note'],'status':'draft',
        'observable_requirements':{
          'observables':[{'name':'rel.occupies','unit':'structured','description':'Original Native device footprint intersection with reviewed path and roadway.'}],
          'context_inputs':[{'name':'path_context','unit':'structured','description':'Reviewed path surface, continuity, adjacency, obstruction and usability context.'}],
          'sweep_dimensions':[{'name':'st.obstruction','unit':'structured','description':'Measured obstruction geometry and overlap with path.'}],
          'landmarks':[],
          'recording_needs':[{'name':'st.bicycle_lane_or_path','unit':'structured','description':'Source-reviewed adjacent path geometry and condition.'},
                             {'name':'st.obstruction','unit':'structured','description':'Source-reviewed obstruction geometry.'},
                             {'name':'rel.occupies','unit':'structured','description':'Native device footprint occupancy.'}],
          'limitations':['Usability remains a qualitative judgment requiring independent original-source review; no numeric cutoff is supplied by this law.']}}
    refs['judgment_observables']=[write('judgment-observables-usable.json',observable)]
    binding={'cell_id':'C230224','actor':ACTOR,'status':'draft',
        'established_contexts':['Frozen cycle-path travel cell; actual path usability remains source-gated.'],
        'law_refs':[{'template_id':TID,'binding_kind':'direct'}], 'context_refs':[],
        'fixed_parameters':[],
        'variable_parameters':[{'name':'path_usable_context','kind':'world_setup','range_or_domain':'Reviewed true/false/unknown path usability','used_by_laws':[LAW]},
          {'name':'observed_occupancy','kind':'subject_behavior','range_or_domain':'Native footprint path/road occupancy','used_by_laws':[LAW]},
          {'name':'commanded_path_choice','kind':'controller','range_or_domain':['path','roadway'],'used_by_laws':[LAW]}]}
    refs['bindings']=write('bindings.json',binding)
    common={'path_usable_context':{'kind':'world_setup','value':True},
            'observed_occupancy':{'kind':'subject_behavior','value':None},
            'commanded_path_choice':{'kind':'controller','value':'path'}}
    base={'case_id':AID+'__neutral_baseline','target_law_id':None,'target_type':'baseline',
          'rationale':'Unselected common source and capture reference; no legal label.',
          'variable_assignments':common,'unresolved_judgment_calls':[],
          'recording_description':REC}
    pair=[]
    for suffix,choice,target in [('probe_01','path','compliant_attempt'),('probe_02','roadway','violating_attempt')]:
        assignments=json.loads(json.dumps(common))
        assignments['commanded_path_choice']['value']=choice
        pair.append({'case_id':AID+'__'+suffix,'target_law_id':LAW,'target_type':target,
            'rationale':'Controlled physical path-choice attempt; legal and usability conclusions remain pending original review.',
            'variable_assignments':assignments,'unresolved_judgment_calls':[J['phrase']],
            'recording_description':REC,'paired_probe_id':AID+'__path_choice',
            'deliberate_differences':['commanded_path_choice'],
            'probe':{'primary_variable':'commanded_path_choice',
                     'comparison_or_standard':'Source-reviewed path versus roadway occupancy on the same adjacent route',
                     'target_value_or_branch':choice},
            'deterministic_branch':{'source_clause':'shall use such path and shall not use the roadway.',
                'judgment_context':[{'phrase':J['phrase'],'note':J['note'],'status':'fixed_assumption',
                    'reason':'Both controlled cases request the same reviewed usable adjacent path; the actual condition is independently checked after Native capture.',
                    'world_setup_refs':['path_usable_context']}]}})
    cases={'cell_id':'C230224','actor':ACTOR,'status':'draft','sweeps_expanded':True,'cases':[base]+pair,
        'sweep_specs':[{'sweep_id':'LVMC-11-40-120-path-usability','target_law_id':LAW,
            'judgment_refs':[J],'status':'incomplete',
            'rationale':'Qualitative usability has no legal numeric cutoff; survey and independent review must establish original path condition.',
            'missing_inputs':['Reviewed original path surface/continuity and usable-obstruction variations from a compatible Native map are not present in frozen inputs.']}]}
    refs['cases']=write('cases.json',cases)
    write('semantic-index.json',{'format':'worker-semantic-delivery','assignment_id':AID,'stages':refs})
    print(json.dumps({'selected_cases':[x['case_id'] for x in pair],'judgment_phrase':J['phrase']},sort_keys=True))


if __name__=='__main__':
    main()
