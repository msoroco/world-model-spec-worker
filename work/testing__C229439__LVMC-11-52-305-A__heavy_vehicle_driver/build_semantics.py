"""Author source-bound LVMC 11.52.305(A) stage proposals."""
import hashlib
import json
from pathlib import Path
from build_constructions import description
from service_parking import CASES
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PROPOSALS = ROOT / 'proposals'
LAW = json.loads((REPO / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())['law']
TEMPLATE = LAW['id'] + '@heavy_vehicle_driver'


def put(name, obj):
    PROPOSALS.mkdir(exist_ok=True)
    path = PROPOSALS / (name + '.json')
    path.write_text(json.dumps(obj, indent=2) + '\n')
    return {'path': 'proposals/' + path.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


VARIABLES = [
    ('commercial_vehicle_status', 'reviewed commercial classification'),
    ('overall_length_ft', 'independently reviewed overall length in ft'),
    ('unladen_weight_lb', 'independently reviewed unladen weight in lb'),
    ('adjacent_place', 'source-verified public school, public park or residence district'),
    ('residential_frontage_ft', 'residential street frontage in ft'),
    ('work_kind', 'actual service, repair, construction, similar essential activity or none'),
    ('work_near', 'engineering worksite placement; not a legal immediate-neighborhood cutoff'),
    ('posted_sign_permission', 'exact sign text and authority'),
    ('expeditious_loading', 'goods or passenger loading in front of relevant property'),
]


def assignments(case):
    values = {'commercial_vehicle_status': True, 'overall_length_ft': case.length_ft,
              'unladen_weight_lb': case.unladen_lb, 'adjacent_place': case.adjacent_kind,
              'residential_frontage_ft': case.frontage_ft, 'work_kind': case.work_kind,
              'work_near': case.work_near, 'posted_sign_permission': case.posted_permission,
              'expeditious_loading': case.loading}
    return {name: {'kind': 'world_setup', 'value': values[name], 'note': domain}
            for name, domain in VARIABLES}


def build():
    relevance = {'cell_id': 'C229439', 'actor': 'heavy_vehicle_driver', 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW['id'], 'quote': LAW['text'],
                                    'applies_to': ['heavy_vehicle_driver'],
                                    'relevance_type': 'direct commercial vehicle parking rule and service exception',
                                    'confidence': 'high',
                                    'notes': 'Park maneuver on a City street adjacent to a sourced public school or other statutory place.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': put('relevance_batch', relevance),
            'relevance': put('relevance', relevance)}
    variables = [{'name': n, 'kind': 'world_setup', 'range_or_domain': d} for n,d in VARIABLES]
    template = {'template_id': TEMPLATE, 'law_id': LAW['id'],
                'actor': 'heavy_vehicle_driver', 'quote': LAW['text'],
                'structure': {
                    'law_id': LAW['id'],
                    'activation': {'condition': 'A commercial vehicle, recreational vehicle, trailer, or vehicle/trailer combination is parked on a street adjacent to a residence district, public school, or public park; length and weight are alternative statutory thresholds. Residence district also requires nonbusiness, mainly residential contiguous frontage.',
                                   'numeric_conditions': [
                                       {'variable':'overall_length_ft','operator':'>=','value':24,'unit':'ft'},
                                       {'variable':'unladen_weight_lb','operator':'>','value':8000,'unit':'lb'},
                                       {'variable':'residential_frontage_ft','operator':'>=','value':300,'unit':'ft'}]},
                    'obligation': {'type': 'must_not', 'description': LAW['text'],
                                   'numeric_conditions': []},
                    'exceptions': [
                        {'trigger':'Authorized posted sign permission', 'effect':'Subsection (A) prohibition does not apply when permitted by posted sign', 'replacement_obligation':None,
                         'source_clause':'as permitted by posted sign'},
                        {'trigger':'Commercial vehicle expeditiously loading or unloading relevant property', 'effect':'Subsection (A) does not apply for that period', 'replacement_obligation':None,
                         'source_clause':'Parked in front of property from which or to which goods or passengers are being picked up or delivered, but only for that period of time during which goods or passengers are being expeditiously loaded or unloaded'},
                        {'trigger':'Commercial vehicle actually used with service, repair, construction or similar essential use within immediate neighborhood', 'effect':'Subsection (A) does not apply', 'replacement_obligation':None,
                         'source_clause':'Being used in conjunction with the performance of service, repair, construction or similar essential use within the immediate neighborhood'}],
                    'timing': {'description': 'Original complete parked interval; loading is limited to the expeditious interval and work use must be active during parking.', 'numeric_conditions': []},
                    'judgment_calls_needed': []},
                'parameter_refs': variables}
    refs['template'] = put('template', template)
    refs['judgment_observables'] = []
    binding = {'cell_id':'C229439','actor':'heavy_vehicle_driver','status':'draft',
               'established_contexts':['City street','park maneuver','parking restriction device'],
               'law_refs':[{'template_id':TEMPLATE,'binding_kind':'direct'}],
               'context_refs':[], 'fixed_parameters':[],
               'variable_parameters':[{**v,'used_by_laws':[LAW['id']]} for v in variables]}
    refs['bindings'] = put('bindings', binding)
    desc = description()
    unresolved = ['Whether the sourced worksite is within the immediate neighborhood is reserved for independent legal review; near/far is an engineering probe.',
                  'Mainly occupied residential frontage, similar essential use, exact sign authority and other section exceptions require independent source review.']
    cases = [{'case_id':ASSIGNMENT+'__baseline','target_law_id':None,'target_type':'baseline',
              'rationale':'Common parked heavy commercial vehicle with independent source references.',
              'variable_assignments':assignments(CASES[0]),'recording_description':desc,
              'unresolved_judgment_calls':unresolved}]
    boundary = {
        'length_23_9ft':('overall_length_ft','activation.numeric_conditions[0]','>=','ft','length_boundary',.1),
        'length_24_0ft':('overall_length_ft','activation.numeric_conditions[0]','>=','ft','length_boundary',.1),
        'length_24_1ft':('overall_length_ft','activation.numeric_conditions[0]','>=','ft','length_boundary',.1),
        'weight_7999lb':('unladen_weight_lb','activation.numeric_conditions[1]','>','lb','weight_boundary',1),
        'weight_8000lb':('unladen_weight_lb','activation.numeric_conditions[1]','>','lb','weight_boundary',1),
        'weight_8001lb':('unladen_weight_lb','activation.numeric_conditions[1]','>','lb','weight_boundary',1),
        'residence_299ft':('residential_frontage_ft','activation.numeric_conditions[2]','>=','ft','residence_boundary',1),
        'residence_300ft':('residential_frontage_ft','activation.numeric_conditions[2]','>=','ft','residence_boundary',1),
        'residence_301ft':('residential_frontage_ft','activation.numeric_conditions[2]','>=','ft','residence_boundary',1)}
    primary_by_name = {'service_school_24ft_8001lb':'work_kind','no_service':'work_kind',
        'repair_near':'work_kind','construction_near':'work_kind','similar_essential_near':'work_kind',
        'service_far':'work_near','posted_permission':'posted_sign_permission',
        'expeditious_loading':'expeditious_loading','public_park':'adjacent_place'}
    for case in CASES:
        cid = ASSIGNMENT+'__'+case.name
        if case.name in boundary:
            variable, ref, op, unit, pair, epsilon = boundary[case.name]
            value=assignments(case)[variable]['value']
            target_type='boundary_probe'
            probe={'primary_variable':variable,'comparison_or_standard':'Exact statutory numeric threshold; other qualifying dimensions and legal context remain separately sourced.',
                   'target_value_or_branch':value,'threshold_ref':ref,'operator':op,'unit':unit,'test_value':value}
            extra={'epsilon_used':{'value':epsilon,'unit':unit,'rationale':'Engineering probe separation around the exact statutory boundary, without legal tolerance.'}}
        else:
            variable=primary_by_name[case.name]
            pair='service_presence' if case.name in ('service_school_24ft_8001lb','no_service') else case.name
            target_type='violating_attempt' if case.name=='no_service' else 'compliant_attempt'
            probe={'primary_variable':variable,'comparison_or_standard':'Source-reviewed service exception and parked interval; no legal finding.',
                   'target_value_or_branch':case.name}
            extra={}
        cases.append({'case_id':cid,'target_law_id':LAW['id'],'target_type':target_type,
                      'rationale':'Measure original parked vehicle, source-backed dimensional and adjacent-place facts, and actual work/loading/sign context without assigning legal liability.',
                      'variable_assignments':assignments(case),'recording_description':desc,
                      'unresolved_judgment_calls':unresolved,
                      'paired_probe_id':pair,'deliberate_differences':[variable],
                      'probe':probe,**extra})
    refs['cases'] = put('cases', {'cell_id':'C229439','actor':'heavy_vehicle_driver',
                                 'status':'draft','cases':cases,'sweep_specs':[]})
    put('semantic-index', {'format':'worker-semantic-delivery','assignment_id':ASSIGNMENT,'stages':refs})

if __name__ == '__main__':
    build()
