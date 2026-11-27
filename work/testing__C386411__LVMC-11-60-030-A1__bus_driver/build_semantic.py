"""Source-faithful semantic stage proposals for bus-stop location probes."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
AID=ROOT.name
LAW='LVMC-11-60-030-A1'
ACTOR='bus_driver'
TEMPLATE=LAW+'@'+ACTOR
OUT=ROOT/'proposals'
OUT.mkdir(exist_ok=True)


def write(name,value):
    path=OUT/name
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    return {'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    assignment=json.loads((REPO/'inputs'/AID/'assignment.json').read_text())
    plan=json.loads((ROOT/'case-plan.json').read_text())
    quote=assignment['law']['text']
    relevance={'cell_id':'C386411','actor':ACTOR,'status':'draft',
               'relevant_laws':[{'law_id':LAW,'quote':quote,'applies_to':[ACTOR],'confidence':'high'}],
               'borderline_excluded':[]}
    relevance_ref=write('relevance.json',relevance)
    write('relevance-batch.json',relevance)
    parameters=[
      {'name':'official_bus_stop_polygon','kind':'world_setup','range_or_domain':'original City Traffic Engineer designated stop boundary and signs','unit':'geometry'},
      {'name':'assigned_route_permitted_locations','kind':'world_setup','range_or_domain':'source-reviewed bus stand, assigned-route origin and destination','unit':'geometry'},
      {'name':'requested_stop_relation','kind':'controller','range_or_domain':'inside or outside reviewed stop polygon','unit':'category'},
      {'name':'observed_bus_body_location','kind':'subject_behavior','range_or_domain':'source-bound original body footprint for complete activity','unit':'geometry'},
      {'name':'conduct','kind':'world_setup','range_or_domain':'stand or park by independent activity review','unit':'category'},
    ]
    template={'template_id':TEMPLATE,'law_id':LAW,'actor':ACTOR,'status':'draft','quote':quote,
      'structure':{'law_id':LAW,
        'activation':{'condition':'Covered operator of non-tour bus stands or parks upon a public street; original status and assigned route reviewed.','numeric_conditions':[]},
        'obligation':{'description':'Do not stand or park on the street except at officially designated bus stop, bus stand, or assigned-route origin/destination designated under Section 11.60.010.','type':'must','numeric_conditions':[]},
        'exceptions':[{'trigger':'tour bus','effect':'outside this paragraph','replacement_obligation':None,'source_clause':'other than a tour bus'}],
        'timing':{'description':'Evaluate full independently reviewed standing or parking activity and Native body position, not one frame.','numeric_conditions':[]},
        'judgment_calls_needed':[]},
      'parameter_refs':parameters}
    template_ref=write('template.json',template)
    binding={'cell_id':'C386411','actor':ACTOR,'status':'draft',
             'law_refs':[{'template_id':TEMPLATE,'binding_kind':'direct'}],
             'context_refs':[],'fixed_parameters':[],
             'variable_parameters':[dict(x,used_by_laws=[LAW]) for x in parameters]}
    binding_ref=write('bindings.json',binding)
    first=json.loads((ROOT/'cases/stand_inside/construction.json').read_text())
    def values(conduct,relation):
        return {'official_bus_stop_polygon':{'kind':'world_setup','value':'source-reviewed stop polygon','unit':'geometry'},
                'assigned_route_permitted_locations':{'kind':'world_setup','value':'source-reviewed bus stand and route termini','unit':'geometry'},
                'requested_stop_relation':{'kind':'controller','value':relation,'unit':'category'},
                'observed_bus_body_location':{'kind':'subject_behavior','value':None,'unit':'geometry'},
                'conduct':{'kind':'world_setup','value':conduct,'unit':'category'}}
    cases=[{'case_id':AID+'__baseline','target_law_id':None,'target_type':'baseline','status':'draft',
            'rationale':'Common source-gated non-tour bus and official bus stop on one-way public street; no original location or legal finding.',
            'variable_assignments':values('stand','inside'),'unresolved_judgment_calls':[],
            'recording_description':first['recording_description']}]
    for case in plan['cases']:
        construction=json.loads((ROOT/'cases'/case['case_id'].split('__')[-1]/'construction.json').read_text())
        cases.append({'case_id':case['case_id'],'target_law_id':LAW,'target_type':'compliant_attempt' if case['location_relation']=='inside' else 'violating_attempt','status':'draft',
          'rationale':'Inside or outside original designated stop must be measured against reviewed boundary; original alternative permitted locations separately checked.',
          'paired_probe_id':'stop_boundary_and_conduct',
          'deliberate_differences':['requested_stop_relation','conduct'],
          'variable_assignments':values(case['conduct'],case['location_relation']),
          'unresolved_judgment_calls':['original designation, standing/parking and alternative-location review'],
          'recording_description':construction['recording_description'],
          'probe':{'primary_variable':'requested_stop_relation','comparison_or_standard':'original reviewed designated stop boundary',
                   'target_value_or_branch':case['location_relation']}})
    cases_ref=write('cases.json',{'cell_id':'C386411','actor':ACTOR,'status':'draft',
                                  'cases':cases,'sweep_specs':[],'sweeps_expanded':True})
    write('semantic-index.json',{'format':'worker-semantic-delivery','assignment_id':AID,
      'status':'complete_source_gated_stop_position_plan',
      'stages':{'relevance_batch':relevance_ref,'relevance':relevance_ref,'template':template_ref,
                'judgment_observables':[],'bindings':binding_ref,'cases':cases_ref}})
    print('four-case canonical semantic chain prepared')


if __name__=='__main__':build()
