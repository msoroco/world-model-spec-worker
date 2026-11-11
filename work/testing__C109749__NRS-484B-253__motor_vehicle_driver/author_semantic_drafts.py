"""Author source-backed draft semantic stages for the selected law and cell."""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
assignment = json.loads((folder.parent.parent/'inputs'/folder.name/'assignment.json').read_text())
law = assignment['law']
law_id, cell_id, actor = (assignment[key] for key in ('law_id','cell_id','actor'))
template_id = law_id+'@'+actor
proposal = folder/'proposals'


def write(name, value):
    (proposal/name).write_text(json.dumps(value, indent=2)+'\n')


relevance = {
    'cell_id':cell_id,'actor':actor,'status':'draft',
    'relevant_laws':[{'law_id':law_id,'quote':law['text'],'applies_to':[actor],
        'relevance_type':'direct selected left-turn duty','confidence':'high',
        'notes':'The frozen cell is an intersection left turn with another vehicle; actual opposing approach and hazard remain to be measured.'}],
    'borderline_excluded':[],
}
write('relevance-batch.json',relevance)
write('relevance.json',relevance)

parameters = [
    ('controller_release_ttc_s','controller','positive engineering seconds; no legal hazard cutoff'),
    ('approach_speed_mps','controller','positive engineering metres per second'),
    ('reciprocal_approach_speed_mps','controller','positive engineering metres per second'),
    ('commanded_approach_speed','controller','positive engineering metres per second'),
    ('commanded_turn_path','controller','authored left-turn waypoint path'),
    ('initial_opposing_in_intersection','subject_behavior','observed boolean from opposing body and sourced junction'),
    ('ego_turn_onset','subject_behavior','observed Native frame'),
    ('reciprocal_stop_outside','subject_behavior','observed boolean from later opposing body and velocity'),
    ('ego_speed','subject_behavior','observed metres per second, never a controller request'),
    ('later_opposing_braking_policy','controller','boolean engineering policy for later opposing target speed'),
]
template = {
    'template_id':template_id,'law_id':law_id,'actor':actor,'status':'draft','quote':law['text'],
    'structure':{
        'law_id':law_id,
        'activation':{'condition':'driver is within an intersection intending to turn left; an opposite-direction vehicle is within the intersection or sufficiently close to pose an immediate hazard',
                      'numeric_conditions':[]},
        'obligation':{'description':'yield right-of-way to the qualifying opposite-direction vehicle before making the left turn',
                      'type':'must','numeric_conditions':[]},
        'exceptions':[{'trigger':'subject has yielded and given a signal when and as required',
                       'effect':'subject may make the left turn',
                       'replacement_obligation':'other opposite-direction drivers approaching the intersection shall yield to the turning vehicle',
                       'source_clause':'but such driver, having so yielded and having given a signal when and as required, may make such left turn and the drivers of all other vehicles approaching the intersection from the opposite direction shall yield the right-of-way to the vehicle making the left turn.'}],
        'timing':{'description':'initial yield precedes the signalled turn; opposing duty follows the subject having yielded and making the turn',
                  'numeric_conditions':[]},
        'judgment_calls_needed':[
            {'phrase':'immediate hazard','note':'No numeric legal time-to-conflict threshold is supplied.'},
            {'phrase':'when and as required','note':'Signal sufficiency depends on other applicable signal rules and original context.'},
            {'phrase':'yield the right-of-way','note':'Observed body and speed histories do not by themselves decide legal priority.'},
        ],
    },
    'parameter_refs':[{'name':name,'kind':kind,'range_or_domain':domain} for name,kind,domain in parameters],
}
write('template.json',template)

common = {
    'status':'draft','template_id':template_id,'limitations':[
        'Actual Native motion, complete body geometry and pixel visibility require original-source review.',
        'These observables do not assign a legal standard or compliance label.',
    ],
}
judgments = [
    {
        'phrase':'immediate hazard','note':'No numeric legal time-to-conflict threshold is supplied.',
        'observables':[
            ('initial_oncoming_in_intersection','boolean','opposing body overlap with sourced junction over time'),
            ('oncoming_speed','m/s','original opposite-direction velocity magnitude over the approach'),
            ('ego_in_intersection','boolean','subject body overlap with sourced junction over the same interval'),
        ],
        'contexts':[('junction_context','structured record','original Native junction and connected opposing routes')],
        'dimensions':[('oncoming_speed','m/s','measured opposing approach speed')],
    },
    {
        'phrase':'when and as required','note':'Signal sufficiency depends on other applicable signal rules and original context.',
        'observables':[
            ('ego_left_indicator','boolean','original left-indicator readback throughout approach and turn'),
            ('ego_heading','deg','original subject heading throughout approach and turn'),
            ('ego_in_intersection','boolean','original subject body overlap with junction at turn onset'),
        ],
        'contexts':[('junction_context','structured record','sourced district, junction and applicable signal-rule context')],
        'dimensions':[('ego_heading','deg','measured subject heading during turn')],
    },
    {
        'phrase':'yield the right-of-way','note':'Observed body and speed histories do not by themselves decide legal priority.',
        'observables':[
            ('ego_in_intersection','boolean','subject body and junction occupancy history'),
            ('initial_oncoming_in_intersection','boolean','initial opposing body and junction occupancy history'),
            ('reciprocal_in_intersection','boolean','later opposing body and junction occupancy history'),
            ('ego_speed','m/s','original subject speed history'),
            ('oncoming_speed','m/s','original initial opposing speed history'),
            ('reciprocal_speed','m/s','original later opposing speed history'),
        ],
        'contexts':[('junction_context','structured record','original junction, lane directions and governing controls')],
        'dimensions':[('ego_speed','m/s','measured subject speed'),('oncoming_speed','m/s','measured initial opposing speed')],
    },
]


def items(rows):
    return [{'name':name,'unit':unit,'description':description} for name,unit,description in rows]


for number, item in enumerate(judgments,1):
    observed = items(item['observables'])
    write(f'judgment-observables-{number}.json',{
        'template_id':template_id,'phrase':item['phrase'],'note':item['note'],'status':'draft',
        'observable_requirements':{
            'observables':observed,'context_inputs':items(item['contexts']),
            'sweep_dimensions':items(item['dimensions']),'landmarks':[],
            'recording_needs':observed,'limitations':common['limitations'],
        },
    })

bindings = {
    'cell_id':cell_id,'actor':actor,'status':'draft',
    'established_contexts':['Frozen C109749 intersection left-turn and other-vehicle cell; actual Native geometry, signal context and approach histories remain to be measured.'],
    'law_refs':[{'template_id':template_id,'binding_kind':'direct'}],
    'context_refs':[],
    'fixed_parameters':[{'name':'selected_cell','value':cell_id,'rationale':'Frozen assignment identity'}],
    'variable_parameters':[{'name':name,'kind':kind,'range_or_domain':domain,'used_by_laws':[law_id]}
                           for name,kind,domain in parameters],
}
write('bindings.json',bindings)
