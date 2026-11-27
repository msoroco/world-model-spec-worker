"""Source-faithful semantic stage proposals for A2 loading-stop alternatives."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
AID=ROOT.name
LAW='LVMC-11-60-030-A2'
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
    relevance={'cell_id':'C378132','actor':ACTOR,'status':'draft',
               'relevant_laws':[{'law_id':LAW,'quote':quote,'applies_to':[ACTOR],'confidence':'high'}],
               'borderline_excluded':[]}
    relevance_ref=write('relevance.json',relevance)
    write('relevance-batch.json',relevance)
    parameters=[
      {'name':'official_permitted_location_polygons','kind':'world_setup','range_or_domain':'source-reviewed City-designated stop, stand, passenger zone and assigned-route endpoints','unit':'geometry'},
      {'name':'observed_bus_body_location','kind':'subject_behavior','range_or_domain':'source-bound original bus footprint throughout stopped interval','unit':'geometry'},
      {'name':'loading_purpose','kind':'subject_behavior','range_or_domain':'independently reviewed passenger, baggage or cargo-only purpose','unit':'category'},
      {'name':'stop_reason','kind':'world_setup','range_or_domain':'independently reviewed ordinary or emergency circumstance','unit':'category'},
      {'name':'bus_class','kind':'world_setup','range_or_domain':'independently reviewed regular or excluded tour bus','unit':'category'},
    ]
    template={'template_id':TEMPLATE,'law_id':LAW,'actor':ACTOR,'status':'draft','quote':quote,
      'structure':{'law_id':LAW,
        'activation':{'condition':'Covered operator of a non-tour bus stops on a street for the purpose of loading or unloading passengers or their baggage.','numeric_conditions':[]},
        'obligation':{'description':'Do not make such a loading stop except at a bus stop, bus stand, passenger loading zone or designated assigned-route origin/destination.','type':'must','numeric_conditions':[]},
        'exceptions':[{'description':'Tour bus excluded from this paragraph.'},{'description':'Case of an emergency.'},{'description':'Officially permitted stop, stand, passenger loading zone or designated assigned-route origin/destination.'}],
        'timing':{'description':'Evaluate independently reviewed stop interval, loading purpose and bus footprint, not one frame.','numeric_conditions':[]},
        'judgment_calls_needed':['bus classification, loading purpose, emergency, designation qualifier scope and location boundaries remain source judgments']},
      'parameter_refs':parameters}
    template_ref=write('template.json',template)
    binding={'cell_id':'C378132','actor':ACTOR,'status':'draft',
             'law_refs':[{'template_id':TEMPLATE,'binding_kind':'direct'}],
             'context_refs':[],'fixed_parameters':[],
             'variable_parameters':[dict(x,used_by_laws=[LAW]) for x in parameters]}
    binding_ref=write('bindings.json',binding)
    first=json.loads((ROOT/'cases/outside_passenger/construction.json').read_text())
    def values(case):
        return {'official_permitted_location_polygons':{'kind':'world_setup','value':'source-reviewed five-place polygon inventory','unit':'geometry'},
                'observed_bus_body_location':{'kind':'subject_behavior','value':case['location_kind'],'unit':'geometry'},
                'loading_purpose':{'kind':'subject_behavior','value':case['loading_purpose'],'unit':'category'},
                'stop_reason':{'kind':'world_setup','value':case['stop_reason'],'unit':'category'},
                'bus_class':{'kind':'world_setup','value':case['bus_class'],'unit':'category'}}
    baseline=plan['cases'][0]
    cases=[{'case_id':AID+'__baseline','target_law_id':None,'target_type':'baseline','status':'draft',
            'rationale':'Common source-gated bus loading-stop street and independent designation review; no original location or legal finding.',
            'variable_assignments':values(baseline),'unresolved_judgment_calls':[],
            'recording_description':first['recording_description']}]
    for case in plan['cases']:
        construction=json.loads((ROOT/'cases'/case['case_id'].split('__')[-1]/'construction.json').read_text())
        cases.append({'case_id':case['case_id'],'target_law_id':LAW,'target_type':'branch_probe','status':'draft',
          'rationale':'Original stopped footprint, purpose, classification and emergency facts must be independently measured; no legal verdict follows from target labels.',
          'paired_probe_id':'loading_location_purpose_exception',
          'deliberate_differences':['observed_bus_body_location','loading_purpose','stop_reason','bus_class'],
          'variable_assignments':values(case),
          'unresolved_judgment_calls':['original designation, passenger/baggage purpose, tour status, emergency and location review'],
          'recording_description':construction['recording_description'],
          'probe':{'primary_variable':'observed_bus_body_location','comparison_or_standard':'original reviewed five-place designation and selected exception facts',
                   'target_value_or_branch':case['location_kind'],'threshold_ref':'none: qualitative source boundary',
                   'operator':'source_measured_place','unit':'geometry','test_value':case['location_kind']}})
    cases_ref=write('cases.json',{'cell_id':'C378132','actor':ACTOR,'status':'draft',
                                  'cases':cases,'sweep_specs':[],'sweeps_expanded':True})
    write('semantic-index.json',{'format':'worker-semantic-delivery','assignment_id':AID,
      'status':'complete_source_gated_loading_stop_plan',
      'stages':{'relevance_batch':relevance_ref,'relevance':relevance_ref,'template':template_ref,
                'judgment_observables':[],'bindings':binding_ref,'cases':cases_ref}})
    print(f"{len(plan['cases'])}-case canonical semantic chain prepared")


if __name__=='__main__':build()
