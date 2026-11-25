"""Author source-faithful canonical semantic proposals for cycle and scooter parking."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
LAW='LVMC-11-40-170'
ACTOR='cycle_or_scooter_operator'
TEXT='It shall be unlawful for any person to park a bicycle, electric bicycle, or electric scooter upon a street other than upon the roadway against the curb or upon the sidewalk in a rack to support the bicycle, electric bicycle, or electric scooter or against a building or at the curb, in such a manner as to afford the least obstruction to pedestrian traffic.'
TID=LAW+'@'+ACTOR
REC=json.loads((HERE/'config.json').read_text())['recording_description']
J={'phrase':'least obstruction','note':'Pedestrian obstruction requires reviewed geometry, pedestrian corridor and parked-device footprint; the law supplies no numerical cutoff.'}


def write(name,obj):
    path=HERE/'proposals'/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
    return {'path':str(path.relative_to(HERE)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance={'cell_id':'C229388','actor':ACTOR,'status':'draft',
        'relevant_laws':[{'law_id':LAW,'quote':TEXT,'applies_to':[ACTOR],
            'relevance_type':'direct','confidence':'high',
            'notes':'Frozen parking cell; actual rack support, device identity, placement and pedestrian corridor require original sources.'}],
        'borderline_excluded':[]}
    refs={'relevance_batch':write('relevance-batch.json',relevance),
          'relevance':write('relevance.json',relevance)}
    template={'template_id':TID,'law_id':LAW,'actor':ACTOR,'quote':TEXT,'status':'draft',
        'structure':{'law_id':LAW,
          'activation':{'condition':'A bicycle, electric bicycle or electric scooter is parked upon a street.','numeric_conditions':[]},
          'obligation':{'type':'must','description':'Park on the roadway against the curb or on the sidewalk in a supporting rack, against a building, or at the curb, with the least obstruction to pedestrian traffic.','numeric_conditions':[]},
          'exceptions':[],
          'timing':{'description':'While the device remains parked; no statutory numeric duration is stated.','numeric_conditions':[]},
          'judgment_calls_needed':[J]},
        'parameter_refs':[{'name':'parking_obstruction_context','kind':'world_setup','range_or_domain':'source-reviewed rack, sidewalk, curb and pedestrian corridor geometry'},
                          {'name':'observed_placement','kind':'subject_behavior','range_or_domain':'Native parked footprint overlap and surface gap'},
                          {'name':'commanded_park_position','kind':'controller','range_or_domain':['rack_clear','rack_overlap']}]}
    refs['template']=write('template.json',template)
    observable={'template_id':TID,'phrase':J['phrase'],'note':J['note'],'status':'draft',
        'observable_requirements':{
          'observables':[{'name':'rel.occupies','unit':'structured','description':'Original Native parked-device footprint intersection with reviewed rack and pedestrian corridor.'}],
          'context_inputs':[{'name':'parking_context','unit':'structured','description':'Reviewed rack support, sidewalk, roadway, curb and pedestrian corridor.'}],
          'sweep_dimensions':[{'name':'rel.surface_gap','unit':'m','description':'Measured parked footprint gap to reviewed pedestrian corridor; no legal cutoff.'}],
          'landmarks':[],
          'recording_needs':[{'name':'st.sidewalk','unit':'structured','description':'Source-reviewed sidewalk and supporting rack geometry.'},
                             {'name':'st.obstruction','unit':'structured','description':'Measured device obstruction relative to pedestrian corridor.'},
                             {'name':'rel.occupies','unit':'structured','description':'Native parked-device footprint occupancy.'}],
          'limitations':['Least obstruction remains a qualitative judgment requiring independent original-source review; no numeric cutoff is supplied by this law.']}}
    refs['judgment_observables']=[write('judgment-observables-obstruction.json',observable)]
    binding={'cell_id':'C229388','actor':ACTOR,'status':'draft',
        'established_contexts':['Frozen bicycle-rack parking cell; actual rack support and pedestrian obstruction remain source-gated.'],
        'law_refs':[{'template_id':TID,'binding_kind':'direct'}], 'context_refs':[],
        'fixed_parameters':[],
        'variable_parameters':[{'name':'parking_obstruction_context','kind':'world_setup','range_or_domain':'Reviewed rack, curb, sidewalk and pedestrian corridor context','used_by_laws':[LAW]},
          {'name':'observed_placement','kind':'subject_behavior','range_or_domain':'Native footprint rack/corridor overlap and surface gap','used_by_laws':[LAW]},
          {'name':'commanded_park_position','kind':'controller','range_or_domain':['rack_clear','rack_overlap'],'used_by_laws':[LAW]}]}
    refs['bindings']=write('bindings.json',binding)
    common={'parking_obstruction_context':{'kind':'world_setup','value':True},
            'observed_placement':{'kind':'subject_behavior','value':None},
            'commanded_park_position':{'kind':'controller','value':'rack_clear'}}
    base={'case_id':AID+'__neutral_baseline','target_law_id':None,'target_type':'baseline',
          'rationale':'Unselected common source and capture reference; no legal label.',
          'variable_assignments':common,'unresolved_judgment_calls':[],
          'recording_description':REC}
    pair=[]
    for suffix,choice,target in [('probe_01','rack_clear','judgment_sweep'),('probe_02','rack_overlap','judgment_sweep')]:
        assignments=json.loads(json.dumps(common))
        assignments['commanded_park_position']['value']=choice
        pair.append({'case_id':AID+'__'+suffix,'target_law_id':LAW,'target_type':target,
            'rationale':'Controlled rack-supported parking position; legal least-obstruction conclusion remains pending original review.',
            'variable_assignments':assignments,'unresolved_judgment_calls':[J['phrase']],
            'recording_description':REC,'paired_probe_id':AID+'__rack_corridor_position',
            'deliberate_differences':['commanded_park_position'],
            'probe':{'primary_variable':'commanded_park_position',
                     'comparison_or_standard':'Source-measured pedestrian corridor overlap for two positions in the same supporting rack',
                     'target_value_or_branch':choice},
            'deterministic_branch':{'source_clause':'upon the sidewalk in a rack to support the bicycle, electric bicycle, or electric scooter or against a building or at the curb, in such a manner as to afford the least obstruction to pedestrian traffic.',
                'judgment_context':[{'phrase':J['phrase'],'note':J['note'],'status':'fixed_assumption',
                    'reason':'Both controlled cases request the same reviewed supporting rack and pedestrian corridor; the actual condition is independently checked after Native capture.',
                    'world_setup_refs':['parking_obstruction_context']}]}})
    cases={'cell_id':'C229388','actor':ACTOR,'status':'draft','sweeps_expanded':True,'cases':[base]+pair,
        'sweep_specs':[{'sweep_id':'LVMC-11-40-170-pedestrian-obstruction','target_law_id':LAW,
            'judgment_refs':[J],'status':'incomplete',
            'rationale':'Qualitative least obstruction has no legal numeric cutoff; survey and independent review must establish original pedestrian conditions.',
            'missing_inputs':['Reviewed original pedestrian traffic and supporting rack geometry are not present in frozen inputs.']}]}
    refs['cases']=write('cases.json',cases)
    write('semantic-index.json',{'format':'worker-semantic-delivery','assignment_id':AID,'stages':refs})
    print(json.dumps({'selected_cases':[x['case_id'] for x in pair],'judgment_phrase':J['phrase']},sort_keys=True))


if __name__=='__main__':
    main()
