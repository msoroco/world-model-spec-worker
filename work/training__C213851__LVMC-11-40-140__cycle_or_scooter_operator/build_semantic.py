"""Author exact-law semantic stages for residence-driveway sidewalk crossing."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
LAW='LVMC-11-40-140'
ACTOR='cycle_or_scooter_operator'
TEXT='The operator of a bicycle, electric bicycle, or electric scooter within a business or residence district entering into or emerging from an alley, driveway or building shall stop such vehicle immediately prior to driving onto a sidewalk or onto the sidewalk area extending across any alleyway, driveway or building, yielding the right-of-way to any pedestrian as may be necessary to avoid collision.'
TID=LAW+'@'+ACTOR
REC=json.loads((HERE/'config.json').read_text())['recording_description']
J=[{'phrase':'immediately prior','note':'The law supplies no numeric stopping distance or dwell time; original boundary, body motion and temporal order need review.'},
   {'phrase':'as may be necessary to avoid collision','note':'Pedestrian position and crossing conflict require original sources and independent judgment; no time-to-conflict cutoff is supplied.'}]


def write(name,obj):
    path=HERE/'proposals'/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
    return {'path':str(path.relative_to(HERE)),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance={'cell_id':'C213851','actor':ACTOR,'status':'draft',
        'relevant_laws':[{'law_id':LAW,'quote':TEXT,'applies_to':[ACTOR],
            'relevance_type':'direct','confidence':'high',
            'notes':'Frozen residence driveway cell; actual district, sidewalk continuation and pedestrian conflict remain source gated.'}],
        'borderline_excluded':[]}
    refs={'relevance_batch':write('relevance-batch.json',relevance),
          'relevance':write('relevance.json',relevance)}
    template={'template_id':TID,'law_id':LAW,'actor':ACTOR,'quote':TEXT,'status':'draft',
        'structure':{'law_id':LAW,
            'activation':{'condition':'Operator of a bicycle, electric bicycle or electric scooter enters into or emerges from an alley, driveway or building in a business or residence district and approaches a sidewalk or continuing sidewalk area.','numeric_conditions':[]},
            'obligation':{'type':'must','description':'Stop immediately before driving onto the sidewalk or continuing sidewalk area, and yield to a pedestrian as necessary to avoid collision.','numeric_conditions':[]},
            'exceptions':[],
            'timing':{'description':'Stop before sidewalk entry and yield at the pedestrian conflict; no statutory numeric duration or distance is supplied.','numeric_conditions':[]},
            'judgment_calls_needed':J},
        'parameter_refs':[{'name':'district_and_driveway','kind':'world_setup',
            'range_or_domain':'source-reviewed residence district and driveway origin'},
            {'name':'travel_direction','kind':'world_setup',
             'range_or_domain':'source-reviewed entering into the driveway across sidewalk'},
            {'name':'sidewalk_and_pedestrian','kind':'world_setup',
             'range_or_domain':'source-reviewed sidewalk continuation and pedestrian conflict'},
            {'name':'controller_mode','kind':'controller',
             'range_or_domain':['stop_and_yield','roll_through']},
            {'name':'observed_stop_and_yield','kind':'subject_behavior',
             'range_or_domain':'Native motion, sidewalk boundary and pedestrian crossing'}]}
    refs['template']=write('template.json',template)
    refs['judgment_observables']=[]
    for i,j in enumerate(J):
        observable={'template_id':TID,'phrase':j['phrase'],'note':j['note'],'status':'draft',
            'observable_requirements':{
                'observables':[{'name':'drv.stopped' if i==0 else 'ru.pedestrian',
                    'unit':'structured',
                    'description':'Original Native rider/pedestrian state joined to reviewed sidewalk boundary.'}],
                'context_inputs':[{'name':'sidewalk_context','unit':'structured',
                    'description':'Reviewed district, origin, sidewalk continuation, boundary and pedestrian conflict.'}],
                'sweep_dimensions':[{'name':'drv.crossing_line' if i==0 else 'drv.time_to_conflict',
                    'unit':'structured','description':'Measured Native approach or conflict state, without legal cutoff.'}],
                'landmarks':[],
                'recording_needs':[{'name':'st.sidewalk','unit':'structured',
                    'description':'Source-reviewed sidewalk continuation and boundary.'},
                    {'name':'ru.pedestrian','unit':'structured',
                    'description':'Original pedestrian position and conflict polygon.'}],
                'limitations':['Original physical boundary, body motion and pedestrian conflict require independent review; no numeric legal threshold is asserted.']}}
        refs['judgment_observables'].append(write(f'judgment-observables-{i+1}.json',observable))
    binding={'cell_id':'C213851','actor':ACTOR,'status':'draft',
        'established_contexts':['Frozen residence district driveway cell; original sidewalk and pedestrian conditions remain source gated.'],
        'law_refs':[{'template_id':TID,'binding_kind':'direct'}],'context_refs':[],
        'fixed_parameters':[],
        'variable_parameters':[{'name':'district_and_driveway','kind':'world_setup',
            'range_or_domain':'Reviewed residence district and driveway','used_by_laws':[LAW]},
            {'name':'travel_direction','kind':'world_setup',
             'range_or_domain':'Reviewed entry into driveway across sidewalk','used_by_laws':[LAW]},
            {'name':'sidewalk_and_pedestrian','kind':'world_setup',
            'range_or_domain':'Reviewed sidewalk continuation and pedestrian conflict','used_by_laws':[LAW]},
            {'name':'controller_mode','kind':'controller',
            'range_or_domain':['stop_and_yield','roll_through'],'used_by_laws':[LAW]},
            {'name':'observed_stop_and_yield','kind':'subject_behavior',
            'range_or_domain':'Native rider and pedestrian crossing histories','used_by_laws':[LAW]}]}
    refs['bindings']=write('bindings.json',binding)
    common={'district_and_driveway':{'kind':'world_setup','value':'residence_driveway'},
        'travel_direction':{'kind':'world_setup','value':'into_driveway'},
        'sidewalk_and_pedestrian':{'kind':'world_setup','value':True},
        'controller_mode':{'kind':'controller','value':'stop_and_yield'},
        'observed_stop_and_yield':{'kind':'subject_behavior','value':None}}
    pair=[]
    for suffix,mode in (('probe_01','stop_and_yield'),('probe_02','roll_through')):
        assignment=json.loads(json.dumps(common))
        assignment['controller_mode']['value']=mode
        pair.append({'case_id':AID+'__'+suffix,'target_law_id':LAW,
            'target_type':'judgment_sweep',
            'rationale':'Controlled source-measured stop and pedestrian-yield contrast; no legal conclusion inferred.',
            'variable_assignments':assignment,
            'unresolved_judgment_calls':[j['phrase'] for j in J],
            'recording_description':REC,
            'paired_probe_id':AID+'__stop_yield_comparison',
            'deliberate_differences':['controller_mode'],
            'probe':{'primary_variable':'controller_mode',
                'comparison_or_standard':'Measured pre-sidewalk cessation and pedestrian conflict under fixed reviewed geometry',
                'target_value_or_branch':mode},
            'deterministic_branch':{'source_clause':'shall stop such vehicle immediately prior to driving onto a sidewalk or onto the sidewalk area extending across any alleyway, driveway or building, yielding the right-of-way to any pedestrian as may be necessary to avoid collision.',
                'judgment_context':[{'phrase':j['phrase'],'note':j['note'],
                    'status':'fixed_assumption',
                    'reason':'Original reviewed sidewalk and pedestrian context is held fixed across the controller comparison; actual motion is audited after capture.',
                    'world_setup_refs':['district_and_driveway','travel_direction','sidewalk_and_pedestrian']} for j in J]}})
    cases={'cell_id':'C213851','actor':ACTOR,'status':'draft','sweeps_expanded':True,
        'cases':[{'case_id':AID+'__neutral_baseline','target_law_id':None,
            'target_type':'baseline','rationale':'Unselected common context reference; no legal label.',
            'variable_assignments':common,'unresolved_judgment_calls':[],
            'recording_description':REC}]+pair,
        'sweep_specs':[{'sweep_id':LAW+'-stop-immediacy-and-pedestrian-conflict',
            'target_law_id':LAW,'judgment_refs':J,'status':'incomplete',
            'rationale':'No numeric legal stopping distance, dwell time or collision-necessity threshold is supplied.',
            'missing_inputs':['Original surveyed sidewalk boundary, bicycle motion and pedestrian conflict are not present in frozen inputs.']}]}
    refs['cases']=write('cases.json',cases)
    write('semantic-index.json',{'format':'worker-semantic-delivery','assignment_id':AID,'stages':refs})
    print(json.dumps({'selected_cases':[x['case_id'] for x in pair]},sort_keys=True))


if __name__=='__main__':
    main()
