"""Author the exact source-grounded semantic proposal chain for two gap probes."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
ASSIGNMENT = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID, CELL_ID, ACTOR = (ASSIGNMENT[key] for key in ('law_id','cell_id','actor'))
TEMPLATE_ID = LAW_ID + '@' + ACTOR
PAIR = AID + '__gap_pair'
DESCRIPTION = json.loads((ROOT / 'selected/primary/construction.json').read_text())['recording_description']
PROPOSALS = ROOT / 'proposals'


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path':str(path.relative_to(ROOT)),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {'cell_id':CELL_ID,'actor':ACTOR,'status':'draft',
             'relevant_laws':[{'law_id':LAW_ID,'quote':LAW['text'],
                               'applies_to':[ACTOR],'relevance_type':'direct',
                               'confidence':'high',
                               'notes':'Frozen caravan-spacing cell; original highway and membership facts require source review.'}],
             'borderline_excluded':[]}
relevance_batch = write('relevance-batch.json', relevance)
relevance_cell = write('relevance.json', relevance)

judgments = [
    {'phrase':'sufficient space',
     'note':'Original complete-body gaps and candidate entrant size are observed; legal sufficiency remains for independent review.'},
    {'phrase':'without danger',
     'note':'Original entrant motion and surrounding traffic are observed; legal danger is not inferred from a static gap.'},
]
template = {'template_id':TEMPLATE_ID,'law_id':LAW_ID,'actor':ACTOR,
            'quote':LAW['text'],'status':'draft',
            'structure':{
                'activation':{'source_clause':'upon any highway outside of a business district in a caravan or motorcade',
                              'description':'Original highway classification, district status and moving caravan membership require source evidence.'},
                'obligation':{'source_clause':'allow sufficient space between each such vehicle or combination of vehicles',
                              'description':'Measure every consecutive complete-body clear space and potential entrant extent; leave legal sufficiency unresolved.',
                              'type':'must'},
                'exceptions':[],
                'timing':{'source_clause':'shall be operated to allow sufficient space',
                          'description':'Space is sampled throughout the original moving-caravan interval.'},
                'judgment_calls_needed':judgments},
            'parameter_refs':[{'name':'caravan_entry_gap','kind':'world_setup',
                               'range_or_domain':[8,30]}]}
template_ref = write('template.json',template)

observables = [
    [('rel.surface_gap','Original complete-body consecutive clear space'),
     ('ru.trailer_or_combination','Original tractor and trailer body identity')],
    [('drv.lane_change_feasible','Original entrant lane transition and body occupancy'),
     ('kin.speed','Original speed of every participant')],
]
judgment_refs = []
for index, (judgment, fields) in enumerate(zip(judgments, observables)):
    needs = [{'name':name,'unit':'structured','description':description}
             for name,description in fields]
    proposal = {'template_id':TEMPLATE_ID,'phrase':judgment['phrase'],
                'note':judgment['note'],'status':'draft',
                'observable_requirements':{
                    'observables':needs,'context_inputs':[],
                    'sweep_dimensions':[],'landmarks':[],
                    'recording_needs':needs,
                    'limitations':['Original body and lane samples do not establish a legal safety threshold.',
                                   'Caravan membership and outside-business-district status need independent original source review.']}}
    judgment_refs.append(write(f'judgment-{index}.json',proposal))

binding = {'cell_id':CELL_ID,'actor':ACTOR,'status':'draft',
           'established_contexts':[{'name':'caravan_spacing',
                                    'source':'Frozen C228508 road/follow/other_vehicle cell and exact law text'}],
           'law_refs':[{'template_id':TEMPLATE_ID,'binding_kind':'direct'}],
           'context_refs':[],'fixed_parameters':[],
           'variable_parameters':[{'name':'caravan_entry_gap','kind':'world_setup',
                                   'range_or_domain':'8 m or 30 m engineered clear-space target; measured source may differ',
                                   'used_by_laws':[LAW_ID]}]}
binding_ref = write('bindings.json',binding)

def case(suffix, gap):
    return {'case_id':AID+'__'+suffix,'target_law_id':LAW_ID,
            'target_type':'judgment_sweep',
            'rationale':f'Observe {gap} m engineered caravan clear-space contrast while retaining legal judgments.',
            'variable_assignments':{'caravan_entry_gap':{'kind':'world_setup','unit':'m','value':gap}},
            'paired_probe_id':PAIR,'deliberate_differences':['caravan_entry_gap'],
            'probe':{'primary_variable':'caravan_entry_gap',
                     'comparison_or_standard':'measured original clear-space contrast, not a legal threshold',
                     'target_value_or_branch':gap},
            'recording_description':DESCRIPTION,
            'unresolved_judgment_calls':[item['phrase'] for item in judgments]}

baseline = {'case_id':AID+'__baseline','target_law_id':None,'target_type':'baseline',
            'rationale':'Unselected shared caravan geometry definition; no legal outcome.',
            'variable_assignments':{'caravan_entry_gap':{'kind':'world_setup','unit':'m','value':30}},
            'recording_description':DESCRIPTION,'unresolved_judgment_calls':[]}
cases = {'format':'worker-case-proposals','cell_id':CELL_ID,'actor':ACTOR,
         'law_id':LAW_ID,'status':'draft','cases':[baseline,case('probe_a',30),case('probe_b',8)],
         'sweep_specs':[{'sweep_id':AID+'__space_and_danger_review',
                         'target_law_id':LAW_ID,'status':'incomplete',
                         'judgment_refs':judgments,
                         'rationale':'Measured gap contrast; legal sufficient-space and danger standards remain source reviewed.',
                         'missing_inputs':['Original physically coupled tow or non-towing group identity review',
                                           'Original outside-business-district and entry-without-danger review']}],
         'sweeps_expanded':True}
cases_ref = write('cases.json',cases)
write('semantic-index.json',{'format':'worker-semantic-delivery','assignment_id':AID,
                             'stages':{'relevance_batch':relevance_batch,'relevance':relevance_cell,
                                       'template':template_ref,'judgment_observables':judgment_refs,
                                       'bindings':binding_ref,'cases':cases_ref}})
print(json.dumps({'case_count':len(cases['cases']),'judgment_count':len(judgments),
                  'semantic_index_sha256':hashlib.sha256((PROPOSALS/'semantic-index.json').read_bytes()).hexdigest()}))
