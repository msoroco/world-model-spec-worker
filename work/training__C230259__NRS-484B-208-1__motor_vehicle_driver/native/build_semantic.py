"""Canonical NRS 484B.208 stages with statutory predicates left for review."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

F = Path(__file__).resolve().parent.parent
R = F.parents[1]
A = F.name
LAW = 'NRS-484B-208-1'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR
PHRASES = [
    ('controlled-access highway', 'Original facility classification requires a source beyond the authored road.'),
    ('knows, or reasonably should know', 'Original posted-limit notice to the driver requires review.'),
    ('traffic conditions, inclement weather, obstructions or hazards make it necessary',
     'Source-observed necessity needs independent judgment.'),
]


def write(name, value):
    path = F/'proposals'/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(F)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


assignment = json.loads((R/'inputs'/A/'assignment.json').read_text())
quote = assignment['law']['text']
original = json.loads((F/'proposals/cases.json').read_text())
selected = original['cases']
desc = selected[0]['recording_description']
relevance = {'cell_id':'C230259','actor':ACTOR,'status':'draft',
    'relevant_laws':[{'law_id':LAW,'quote':quote,'applies_to':[ACTOR],
        'relevance_type':'specific_match','confidence':'medium',
        'notes':'Two same-direction lanes and rear overtake are constructed; facility, notice and exceptions remain review questions.'}],
    'borderline_excluded':[]}
exceptions = [
    ('Overtaking another vehicle proceeding in the same direction', 'No subject overtake is requested; original scene review pending.'),
    ('Preparing for a left turn at an intersection', 'No left turn is requested; actual road context pending.'),
    ('Traveling in a lane designated for the use of high-occupancy vehicles', 'HOV designation and eligibility require original source and referenced law review.'),
    ('Engaged in the construction, maintenance or repair of the highway', 'Worker duty requires evidence beyond actor motion.'),
    ('traffic conditions, inclement weather, obstructions or hazards make it necessary', 'Necessity is qualitative.'),
    ('official traffic control device or the directions given by a peace officer', 'Control and direction source review pending.'),
    ('authorized emergency vehicle in the course of official duties', 'Authorization and duty cannot be inferred from a blueprint.'),
    ('within the geographical limits of a city or town', 'Location boundary requires independent geospatial source.')]
template = {'template_id':TEMPLATE,'law_id':LAW,'actor':ACTOR,
    'status':'draft','quote':quote,
    'structure':{'activation':{'source_clause':'on a controlled-access highway which has two or more clearly marked lanes for traveling in the same direction',
        'description':'Original facility classification and marked-lane map readback.'},
        'obligation':{'source_clause':'may not continue to operate a motor vehicle in the extreme left lane',
        'description':'Source-join slow subject, faster rear overtake and post-crossing lane occupancy.'},
        'exceptions':[{'source_clause':phrase,'description':note}
                      for phrase,note in exceptions],
        'timing':{'source_clause':'is being overtaken in that lane from the rear',
            'description':'Original 600-frame rear-crossing interval.'},
        'judgment_calls_needed':[{'phrase':phrase,'note':note}
                                 for phrase,note in PHRASES]},
    'parameter_refs':[]}
bindings = {'cell_id':'C230259','actor':ACTOR,'status':'draft',
    'established_contexts':[],'law_refs':[{'template_id':TEMPLATE,
    'binding_kind':'direct'}],'context_refs':[],'fixed_parameters':[],
    'variable_parameters':[{'name':'slow_extreme_left_lane_continuation',
        'kind':'controller','range_or_domain':'true or false; measured from original lane readback',
        'used_by_laws':[LAW]},
        {'name':'road_and_rear_overtake','kind':'world_setup',
         'range_or_domain':'same authored road, speeds, weather and cameras',
         'used_by_laws':[LAW]}]}
baseline = {'case_id':A+'__baseline','target_law_id':None,
    'target_type':'baseline','rationale':'Unselected neutral two-lane context.',
    'variable_assignments':deepcopy(selected[0]['variable_assignments']),
    'recording_description':desc,
    'unresolved_judgment_calls':[phrase for phrase,_ in PHRASES]}
baseline['variable_assignments']['slow_extreme_left_lane_continuation']['value'] = None
for case in selected:
    case['unresolved_judgment_calls'] = [phrase for phrase,_ in PHRASES]
cases = {'format':'worker-case-proposals','cell_id':'C230259','actor':ACTOR,
    'law_id':LAW,'status':'draft','cases':[baseline,*selected],
    'sweep_specs':[{'sweep_id':A+'__notice_and_necessity_review',
        'target_law_id':LAW,'status':'incomplete',
        'judgment_refs':[{'phrase':phrase,'note':note}
                         for phrase,note in PHRASES],
        'rationale':'Selected lane-continuation pair measures motion; statutory activation and exceptions require separate sources.',
        'missing_inputs':['Original controlled-access and posted-limit authority',
                          'Independent notice, geographic and subsection 2 review']}],
    'sweeps_expanded':True}
refs = {'relevance_batch':write('relevance_batch.json',relevance),
        'relevance':write('relevance.json',relevance),
        'template':write('template.json',template)}
judgment = []
for index,(phrase,note) in enumerate(PHRASES):
    obj = {'template_id':TEMPLATE,'phrase':phrase,'note':note,'status':'draft',
        'observable_requirements':{'observables':[{'name':'slow_extreme_left_lane_continuation',
            'unit':'structured','description':'Original actor and map lane relation.'}],
        'context_inputs':[{'name':'left_lane_statutory_context','unit':'structured',
            'description':'Facility, posting, driver notice and subsection 2 review sources.'}],
        'sweep_dimensions':[],'landmarks':[],
        'recording_needs':[{'name':'rear_overtake_crossing','unit':'structured',
            'description':'Original faster rear actor crossing and lane history.'}],
        'limitations':['Motion does not decide facility classification, notice or an exception.',
                       'Original physical and independent legal review pending.']}}
    judgment.append(write(f'judgment_observables_{index}.json',obj))
refs['judgment_observables'] = judgment
refs['bindings'] = write('bindings.json',bindings)
refs['cases'] = write('cases.json',cases)
write('semantic-index.json',{'format':'worker-semantic-delivery',
    'assignment_id':A,'stages':refs})
print(json.dumps({'stages':len(refs),'selected':len(selected)}))
