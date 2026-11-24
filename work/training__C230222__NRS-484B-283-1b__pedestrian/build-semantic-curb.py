"""Author six exact-law canonical draft stages for two curb departures."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ASSIGNMENT=json.loads((ROOT/'inputs'/HERE.name/'assignment.json').read_text())
LAW=ASSIGNMENT['law_id']
ACTOR=ASSIGNMENT['actor']
CELL=ASSIGNMENT['cell_id']
QUOTE=ASSIGNMENT['law']['text']
TEMPLATE=LAW+'@'+ACTOR
PHRASE='so close that it is impossible for the driver to yield'
NOTE='Actual driver capability and statutory impossibility require original vehicle response and independent judgment; a conditional stopping range is an engineering diagnostic.'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def main():
    folder=HERE/'proposals'
    relevance={'cell_id':CELL,'actor':ACTOR,'status':'draft',
               'relevant_laws':[{'law_id':LAW,'quote':QUOTE,'applies_to':[ACTOR],
                                 'relevance_type':'specific_match','confidence':'medium',
                                 'notes':'Curb departure into approaching vehicle path; source geometry and exception applicability require original review.'}],
               'borderline_excluded':[]}
    for name in ('relevance_batch','relevance'):
        write(folder/(name+'.json'),relevance)
    template={'template_id':TEMPLATE,'law_id':LAW,'actor':ACTOR,'status':'draft','quote':QUOTE,
              'structure':{
                  'activation':{'description':'Pedestrian leaves curb or other place of safety into an approaching vehicle path.',
                                'source_clause':'leave a curb or other place of safety and walk or run into the path of a vehicle'},
                  'obligation':{'description':'Do not suddenly enter when the vehicle is too close for its driver to yield.',
                                'source_clause':'A pedestrian shall not suddenly leave'},
                  'exceptions':[{'source_clause':QUOTE.split(':',1)[0],
                                 'description':'Review the cited statutory conditions and original scene before applying this clause.'}],
                  'timing':{'description':'Use the frame bracket for departure and roadway/path entry, with original approaching-vehicle state at that instant.',
                            'source_clause':'walk or run into the path of a vehicle'},
                  'judgment_calls_needed':[{'phrase':PHRASE,'note':NOTE}]},
              'parameter_refs':[]}
    write(folder/'template.json',template)
    observed={'template_id':TEMPLATE,'phrase':PHRASE,'note':NOTE,'status':'draft',
              'observable_requirements':{
                  'observables':[{'name':'drv.stopping_distance','unit':'m',
                                  'description':'Original pedestrian footprint and vehicle state joined at roadway entry; retain conditional assumption range.'}],
                  'context_inputs':[{'name':'introductory_exceptions','unit':'structured',
                                     'description':'Independent exact-text and original source applicability review.'}],
                  'sweep_dimensions':[],'landmarks':[],
                  'recording_needs':[{'name':'drv.stopping_distance','unit':'m',
                                      'description':'Original Native motion, vehicle response and original pixels.'}],
                  'limitations':['Assumed reaction/deceleration cannot establish actual driver capability or statutory impossibility.']}}
    write(folder/'judgment_observables_0.json',observed)
    binding={'cell_id':CELL,'actor':ACTOR,'status':'draft','established_contexts':[],
             'law_refs':[{'template_id':TEMPLATE,'binding_kind':'direct'}],
             'context_refs':[],'fixed_parameters':[],
             'variable_parameters':[
                 {'name':'requested_curb_departure_s','kind':'world_setup',
                  'range_or_domain':'0.5 s or 3.5 s; construction request only','used_by_laws':[LAW]},
                 {'name':'measured_driver_yield_feasibility','kind':'subject_behavior',
                  'range_or_domain':'original source-joined vehicle response and pedestrian entry bracket; judgment unresolved',
                  'used_by_laws':[LAW]},
                 {'name':'authored_marked_crossing_relation','kind':'world_setup',
                  'range_or_domain':'inside or outside the authored marking; original paint and right-of-way unverified',
                  'used_by_laws':[LAW]},
                 {'name':'authored_overhead_survey_target_presence','kind':'world_setup',
                  'range_or_domain':'authored bridge-type survey target present or absent; original pedestrian overhead crossing and access unverified',
                  'used_by_laws':[LAW]}]}
    write(folder/'bindings.json',binding)
    plan=json.loads((HERE/'case-plan.json').read_text())
    recording=json.loads((HERE/'v2-primary/probe_1/construction.json').read_text())['recording_description']
    def assignments(value):
        return {'requested_curb_departure_s':{'kind':'world_setup','value':value},
                'measured_driver_yield_feasibility':{'kind':'subject_behavior','value':None}}
    cases=[{'case_id':HERE.name+'__baseline','target_law_id':None,
            'target_type':'baseline','rationale':'Shared authored curb geometry with no selected departure request.',
            'variable_assignments':assignments(None),'recording_description':recording,
            'unresolved_judgment_calls':[PHRASE]}]
    for item in plan['cases']:
        if '__crossref_lvmc_11_30_060_a_' in item['case_id']:
            label=item['case_id'].rsplit('_',1)[-1]
            construction=json.loads((HERE/'crossref-060a-native'/label/'construction.json').read_text())
            cases.append({'case_id':item['case_id'],'target_law_id':LAW,
                      'target_type':'exception_context',
                      'rationale':'Compare source footprint inside versus outside the authored marked crossing; original paint and right-of-way remain unverified.',
                      'paired_probe_id':'c230222-crossref-060a-pair',
                      'deliberate_differences':['authored_marked_crossing_relation'],
                      'probe':{'primary_variable':'authored_marked_crossing_relation',
                               'comparison_or_standard':'source footprint versus authored marking at first curb entry',
                               'target_value_or_branch':label},
                      'variable_assignments':{**assignments(.5),
                          'authored_marked_crossing_relation':{'kind':'world_setup','value':label}},
                      'recording_description':construction['recording_description'],
                      'unresolved_judgment_calls':[PHRASE]})
            continue
        if '__crossref_lvmc_11_30_060_b_' in item['case_id']:
            label=item['case_id'].split('__crossref_lvmc_11_30_060_b_',1)[1]
            construction=json.loads((HERE/'crossref-060b-native'/label/'construction.json').read_text())
            cases.append({'case_id':item['case_id'],'target_law_id':LAW,
                      'target_type':'exception_context',
                      'rationale':'Compare authored overhead survey target presence; actual pedestrian overpass visibility and access require original Native survey.',
                      'paired_probe_id':'c230222-crossref-060b-pair',
                      'deliberate_differences':['authored_overhead_survey_target_presence'],
                      'probe':{'primary_variable':'authored_overhead_survey_target_presence',
                               'comparison_or_standard':'original road geometry, infrastructure pixels and pedestrian access review',
                               'target_value_or_branch':label},
                      'variable_assignments':{**assignments(.5),
                          'authored_overhead_survey_target_presence':{'kind':'world_setup','value':label}},
                      'recording_description':construction['recording_description'],
                      'unresolved_judgment_calls':[PHRASE]})
            continue
        value=.5 if item['case_id'].endswith('probe_1') else 3.5
        construction=json.loads((HERE/'v2-primary'/item['case_id'].rsplit('__',1)[-1]/'construction.json').read_text())
        cases.append({'case_id':item['case_id'],'target_law_id':LAW,
                      'target_type':'boundary_probe',
                      'rationale':'Compare original curb departure and approaching vehicle response with road, driver policy and capture fixed; retain judgment unresolved.',
                      'paired_probe_id':'c230222-curb-departure-pair',
                      'deliberate_differences':['requested_curb_departure_s'],
                      'probe':{'primary_variable':'requested_curb_departure_s',
                               'comparison_or_standard':'original pedestrian/vehicle state at first roadway entry',
                               'target_value_or_branch':value},
                      'variable_assignments':assignments(value),
                      'recording_description':construction['recording_description'],
                      'unresolved_judgment_calls':[PHRASE]})
    write(folder/'cases.json',{'cell_id':CELL,'actor':ACTOR,'status':'draft','cases':cases,
                               'sweep_specs':[{'sweep_id':'c230222-driver-yield-judgment',
                                               'target_law_id':LAW,
                                               'judgment_refs':[{'phrase':PHRASE,'note':NOTE}],
                                               'rationale':'No numeric legal boundary can be inferred from engineering stopping assumptions; original vehicle response and independent applicability review are required.',
                                               'status':'incomplete',
                                               'missing_inputs':['Original Native vehicle/pedestrian motion, source pixels and independent driver-capability judgment.']}],
                               'sweeps_expanded':True})
    stages={}
    for name in ('relevance_batch','relevance','template','judgment_observables_0','bindings','cases'):
        path=folder/(name+'.json')
        ref={'path':'proposals/'+name+'.json','sha256':sha(path)}
        if name=='judgment_observables_0': stages['judgment_observables']=[ref]
        else: stages[name]=ref
    write(folder/'semantic-index.json',{'format':'worker-semantic-delivery',
                                        'assignment_id':HERE.name,'stages':stages})
    print(json.dumps({'semantic_cases':len(cases),'judgment_status':'unresolved'}))


if __name__=='__main__':
    main()
