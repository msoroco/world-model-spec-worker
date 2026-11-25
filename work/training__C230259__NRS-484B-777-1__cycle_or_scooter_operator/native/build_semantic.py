"""Build exact-law canonical stages with qualitative judgment left open."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
F=Path(__file__).resolve().parent.parent
R=F.parents[1]
A=F.name
LAW='NRS-484B-777-1'
CELL='C230259'
ACTOR='cycle_or_scooter_operator'
TEMPLATE=LAW+'@'+ACTOR
PHRASES=[
 ('as near to the right side of the roadway as practicable','Original right edge, bicycle footprint and feasibility context require review.'),
 ('exercising due care when passing a standing vehicle','Original passing interval and clearance are observations, not a due-care threshold.'),
 ('When doing so would not be safe','Original hazards and lane width require independent safety review.'),
]

def write(name,value):
    p=F/'proposals'/name
    p.write_text(json.dumps(value,indent=2)+'\n')
    return {'path':str(p.relative_to(F)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

assignment=json.loads((R/'inputs'/A/'assignment.json').read_text())
quote=assignment['law']['text']
original=json.loads((F/'proposals/cases.json').read_text())
selected=original['cases']
desc=selected[0]['recording_description']
relevance={'cell_id':CELL,'actor':ACTOR,'status':'draft',
           'relevant_laws':[{'law_id':LAW,'quote':quote,'applies_to':[ACTOR],
                             'relevance_type':'specific_match','confidence':'medium',
                             'notes':'Bicycle operator on roadway; exact exceptions and safety remain open.'}],
           'borderline_excluded':[]}
template={'template_id':TEMPLATE,'law_id':LAW,'actor':ACTOR,'status':'draft','quote':quote,
          'structure':{'activation':{'source_clause':'Every person operating a bicycle, an electric bicycle or an electric scooter upon a roadway',
                                      'description':'Observe original bicycle operator and roadway location.'},
                       'obligation':{'source_clause':'ride as near to the right side of the roadway as practicable, exercising due care when passing a standing vehicle',
                                     'description':'Source-join position and standing-vehicle passing; no numeric legal threshold.'},
                       'exceptions':[{'source_clause':'When traveling at a lawful rate of speed commensurate with the speed of any nearby traffic',
                                      'description':'Nearby traffic and lawful rate require review.'},
                                     {'source_clause':'When preparing to turn left','description':'Original turn preparation requires review.'},
                                     {'source_clause':'When doing so would not be safe','description':'Original safety context requires review.'}],
                       'timing':{'source_clause':'upon a roadway','description':'Full original 600-frame road interval.'},
                       'judgment_calls_needed':[{'phrase':p,'note':n} for p,n in PHRASES]},
          'parameter_refs':[]}
bindings={'cell_id':CELL,'actor':ACTOR,'status':'draft','established_contexts':[],
          'law_refs':[{'template_id':TEMPLATE,'binding_kind':'direct'}], 'context_refs':[],
          'fixed_parameters':[],
          'variable_parameters':[{'name':'requested_cycle_center_y_m','kind':'controller',
                                  'range_or_domain':'-2.65 or -1.45 m engineering contrast; actual footprint measured',
                                  'used_by_laws':[LAW]},
                                 {'name':'route_and_standing_vehicle','kind':'world_setup',
                                  'range_or_domain':'same authored road, standing vehicle, weather and traffic context',
                                  'used_by_laws':[LAW]}]}
baseline={'case_id':A+'__baseline','target_law_id':None,'target_type':'baseline',
          'rationale':'Neutral unselected bicycle and standing-vehicle road context.',
          'variable_assignments':deepcopy(selected[0]['variable_assignments']),
          'recording_description':desc,
          'unresolved_judgment_calls':[p for p,n in PHRASES]}
baseline['variable_assignments']['requested_cycle_center_y_m']['value']=None
for case in selected:
    case['unresolved_judgment_calls']=[p for p,n in PHRASES]
cases={'format':'worker-case-proposals','cell_id':CELL,'actor':ACTOR,'law_id':LAW,'status':'draft',
       'cases':[baseline,*selected],
       'sweep_specs':[{'sweep_id':A+'__position_safety_review','target_law_id':LAW,'status':'incomplete',
                       'judgment_refs':[{'phrase':p,'note':n} for p,n in PHRASES],
                       'rationale':'Selected lateral pair is an observation contrast; legal practicability, due care and safety remain unresolved.',
                       'missing_inputs':['Original physical bicycle and standing-vehicle pixels',
                                         'Independent exception, lane-width, practicability and due-care review']}],
       'sweeps_expanded':True}
refs={'relevance_batch':write('relevance_batch.json',relevance),
      'relevance':write('relevance.json',relevance),
      'template':write('template.json',template)}
judgment=[]
for i,(phrase,note) in enumerate(PHRASES):
    obj={'template_id':TEMPLATE,'phrase':phrase,'note':note,'status':'draft',
         'observable_requirements':{'observables':[{'name':'cycle_lateral_distance_from_right_edge','unit':'structured',
             'description':'Source-joined original bicycle body and right roadway edge.'}],
             'context_inputs':[{'name':'right_edge_pass_context','unit':'structured',
             'description':'Original standing vehicle, lane width, nearby traffic, hazards and turn intent.'}],
             'sweep_dimensions':[],'landmarks':[],
             'recording_needs':[{'name':'standing_vehicle_clearance','unit':'structured',
             'description':'Original 600-frame standing-vehicle pass measurement.'}],
             'limitations':['Distances do not decide practicability, due care, or a statutory safety exception.',
                            'Original physical and independent legal review pending.']}}
    judgment.append(write(f'judgment_observables_{i}.json',obj))
refs['judgment_observables']=judgment
refs['bindings']=write('bindings.json',bindings)
refs['cases']=write('cases.json',cases)
write('semantic-index.json',{'format':'worker-semantic-delivery','assignment_id':A,'stages':refs})
print(json.dumps({'stages':len(refs),'selected':len(selected)}))
