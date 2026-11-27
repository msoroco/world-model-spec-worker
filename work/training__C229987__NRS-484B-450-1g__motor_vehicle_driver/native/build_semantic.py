"""Build source-literal canonical stage proposals for this signal approach."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
repo = root.parents[1]
source = json.loads((repo/'inputs'/root.name/'assignment.json').read_text())
folder = root/'proposals'
folder.mkdir(exist_ok=True)
law_id = source['law_id']
cell_id = source['cell_id']
actor = source['actor']
text = source['law']['text']

def put(name, value):
    path = folder/(name+'.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')
    return {'path': 'proposals/'+path.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

relevance = {'cell_id':cell_id, 'actor':actor, 'status':'draft',
             'relevant_laws':[{'law_id':law_id, 'quote':text,
                               'applies_to':[actor], 'relevance_type':'specific_match',
                               'confidence':'high',
                               'notes':'Exact roadside official traffic signal approach restriction for the driver.'}],
             'borderline_excluded':[]}
references = {'relevance_batch':put('relevance_batch',relevance),
              'relevance':put('relevance',relevance)}
params = [
    {'name':'requested_front_gap_ft','kind':'controller','range_or_domain':'25, 30 or 35 feet requested; actual footprint independently measured'},
    {'name':'activity_mode','kind':'controller','range_or_domain':'stop, stand or park attempt; original classification independently reviewed'},
    {'name':'exception_context_request','kind':'controller','range_or_domain':'none, necessary conflict, other law, police direction or official device direction'},
    {'name':'observed_signal_approach_state','kind':'subject_behavior','range_or_domain':'original footprint, velocity, signal location and source context or unknown'},
]
template = {'template_id':law_id+'@'+actor, 'law_id':law_id, 'actor':actor,
            'status':'draft', 'quote':text,
            'structure':{'law_id':law_id,
                         'activation':{'condition':'Vehicle stops, stands or parks within 30 feet upon the approach to an official traffic-control signal located at the side of a highway.',
                                       'numeric_conditions':[{'variable':'approach distance to signal','operator':'<','value':30,'unit':'ft','source_clause':'Within 30 feet upon the approach'}]},
                         'obligation':{'description':'Do not stop, stand or park in the specified approach zone unless a source exception applies.',
                                       'type':'must_not','numeric_conditions':[]},
                         'exceptions':[
                             {'trigger':'Necessary to avoid conflict with other traffic','effect':'Exception when necessity is established from original traffic evidence.','replacement_obligation':'Retain original traffic evidence for independent review.','source_clause':'except when necessary to avoid conflict with other traffic'},
                             {'trigger':'In compliance with law','effect':'Exception when another law actually governs the activity.','replacement_obligation':'Retain source authority for independent review.','source_clause':'in compliance with law'},
                             {'trigger':'Directions of a police officer','effect':'Exception when an actual police direction applies.','replacement_obligation':'Retain original officer direction evidence for review.','source_clause':'the directions of a police officer'},
                             {'trigger':'Official traffic-control device','effect':'Exception when an official device direction applies.','replacement_obligation':'Retain original device authority and indication evidence for review.','source_clause':'official traffic-control device'}],
                         'timing':{'description':'Observe the complete interval of stop, stand or park on the signal approach.','numeric_conditions':[]},
                         'judgment_calls_needed':[]}, 'parameter_refs':params}
references['template'] = put('template',template)
references['judgment_observables'] = []
binding = {'cell_id':cell_id, 'actor':actor, 'status':'draft', 'established_contexts':[],
           'law_refs':[{'template_id':template['template_id'],'binding_kind':'direct'}],
           'context_refs':[], 'fixed_parameters':[],
           'variable_parameters':[dict(p,used_by_laws=[law_id]) for p in params]}
references['bindings'] = put('bindings',binding)
references['cases'] = {'path':'proposals/cases.json',
                       'sha256':hashlib.sha256((folder/'cases.json').read_bytes()).hexdigest()}
put('semantic-index',{'format':'worker-semantic-delivery','assignment_id':root.name,'stages':references})
