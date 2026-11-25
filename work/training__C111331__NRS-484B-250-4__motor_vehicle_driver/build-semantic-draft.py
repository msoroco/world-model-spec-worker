"""Author a source-quoted canonical draft and expose incomplete judgment sweeps."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
SOURCE=REPO/'inputs'/ROOT.name/'assignment.json'
ASSIGNMENT=json.loads(SOURCE.read_text())
LAW=ASSIGNMENT['law'];LAW_ID=ASSIGNMENT['law_id'];ACTOR=ASSIGNMENT['actor']
CELL=ASSIGNMENT['cell_id'];TEMPLATE=LAW_ID+'@'+ACTOR
PROPOSALS=ROOT/'proposals'


def write(name,value):
    path=PROPOSALS/name
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    return {'path':'proposals/'+name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


text=LAW['text']
quote=text
relevance={'cell_id':CELL,'actor':ACTOR,'status':'draft',
    'relevant_laws':[{'law_id':LAW_ID,'quote':quote,'applies_to':[ACTOR],
        'relevance_type':'direct','confidence':'high',
        'notes':'The selected subsection governs an entering driver at installed uncovered inoperative vehicular signals.'}],
    'borderline_excluded':[]}
relevance_ref=write('relevance.json',relevance)
batch_ref=write('relevance-batch.json',relevance)
phrases=[
    ('point nearest the intersection where the driver has a view of approaching traffic on the through highway',
     'Original observer perspective and approaching traffic pixels are needed for the no-line/no-crosswalk branch.'),
    ('proceed cautiously',
     'Retain original speed, body trajectory and pixels; no numeric legal threshold is specified.'),
    ('yielding to vehicles which have previously completed a stop or are within the intersection',
     'Retain both actor histories, body-to-junction occupancy and release order.'),
]
template={'template_id':TEMPLATE,'law_id':LAW_ID,'actor':ACTOR,'quote':quote,'status':'draft',
    'structure':{'law_id':LAW_ID,
        'activation':{'condition':'Installed uncovered vehicular traffic-control signal is inoperative at entry',
                      'numeric_conditions':[]},
        'obligation':{'description':'Stop at the governing hierarchy reference, then proceed cautiously and yield to prior stoppers or vehicles within the intersection',
                      'type':'must','numeric_conditions':[]},
        'exceptions':[],
        'timing':{'description':'Signal state at entry; stop before entry; yield after such stop',
                  'numeric_conditions':[]},
        'judgment_calls_needed':[{'phrase':phrase,'note':note} for phrase,note in phrases]},
    'parameter_refs':[{'name':name,'kind':kind,'range_or_domain':domain} for name,kind,domain in (
        ('commanded_stop_response','controller',['stop','no_stop']),
        ('governing_stop_reference','world_setup',['marked_line','crosswalk','visible_point']),
        ('commanded_release_order','controller',['normal','yield','prior','inside']),
        ('other_vehicle_context','world_setup',['approaching','prior_stop','inside']))]}
template_ref=write('template.json',template)
judgment_refs=[]
for i,(phrase,note) in enumerate(phrases):
    requirement={'template_id':TEMPLATE,'phrase':phrase,'note':note,'status':'draft',
        'observable_requirements':{'observables':[{'name':'ego_front','unit':'structured',
            'description':'Original frame-indexed vehicle body location relative to the governing reference.'}],
            'context_inputs':[],'sweep_dimensions':[],'landmarks':[],
            'recording_needs':[{'name':'ego_front','unit':'structured',
                'description':'Original vehicle body position and frame join.'}],
            'limitations':[note,'Camera pixels, other-actor history and statutory judgment need independent original review.']}}
    judgment_refs.append(write(f'judgment_observables_{i}.json',requirement))
binding={'cell_id':CELL,'actor':ACTOR,'status':'draft',
    'established_contexts':['Authored OpenDRIVE two-entrance signal intersection; Native readback remains required'],
    'law_refs':[{'template_id':TEMPLATE,'binding_kind':'direct'}],
    'context_refs':[],
    'fixed_parameters':[{'name':'signal_outage_request','value':'Off',
        'rationale':'Every selected comparison requests installed uncovered inoperative governing heads; original state/pixels remain unverified.'}],
    'variable_parameters':[{'name':name,'kind':kind,'range_or_domain':domain,
        'used_by_laws':[LAW_ID]} for name,kind,domain in (
        ('commanded_stop_response','controller',['stop','no_stop']),
        ('governing_stop_reference','world_setup',['marked_line','crosswalk','visible_point']),
        ('commanded_release_order','controller',['normal','yield','prior','inside']),
        ('other_vehicle_context','world_setup',['approaching','prior_stop','inside']))]}
binding_ref=write('bindings.json',binding)

manifest=json.loads((ROOT/'stop-reference-construction-manifest.json').read_text())
by_suffix={entry['id']:entry for entry in manifest['cases']}
assignments={
    'controlled_1':('stop','marked_line','normal','approaching'),
    'controlled_2':('no_stop','marked_line','normal','approaching'),
    'crosswalk_stop':('stop','crosswalk','normal','approaching'),
    'crosswalk_no_stop':('no_stop','crosswalk','normal','approaching'),
    'visible_point_stop':('stop','visible_point','normal','approaching'),
    'visible_point_no_stop':('no_stop','visible_point','normal','approaching'),
    'prior_stop_yield':('stop','marked_line','yield','prior_stop'),
    'prior_stop_no_yield':('stop','marked_line','prior','prior_stop'),
    'inside_vehicle_no_yield':('stop','marked_line','inside','inside'),
}
cases=[]
recording=json.loads((ROOT/'selected-candidates/controlled_1/primary/construction.json').read_text())['recording_description']
def assignment(value,kind):return {'kind':kind,'value':value,'unit':'categorical'}
for suffix,values in assignments.items():
    entry=by_suffix[suffix]
    cases.append({'case_id':entry['case_id'],'target_law_id':LAW_ID,
        'target_type':'judgment_sweep',
        'rationale':'Exact diagnostic branch for '+suffix+'; legal judgment remains unresolved.',
        'variable_assignments':{
            'commanded_stop_response':assignment(values[0],'controller'),
            'governing_stop_reference':assignment(values[1],'world_setup'),
            'commanded_release_order':assignment(values[2],'controller'),
            'other_vehicle_context':assignment(values[3],'world_setup')},
        'paired_probe_id':'reference_'+suffix,
        'deliberate_differences':['commanded_stop_response','governing_stop_reference',
                                  'commanded_release_order','other_vehicle_context'],
        'probe':{'primary_variable':'commanded_stop_response',
            'comparison_or_standard':'Five exact case-plan comparisons',
            'target_value_or_branch':suffix},
        'unresolved_judgment_calls':[phrase for phrase,_ in phrases],
        'recording_description':recording})
baseline=dict(cases[0]);baseline['case_id']=ROOT.name+'__baseline';baseline['target_law_id']=None
baseline['target_type']='baseline';baseline['rationale']='Unselected shared neutral reference; no legal outcome asserted.'
baseline.pop('paired_probe_id');baseline.pop('deliberate_differences');baseline.pop('probe')
cases.insert(0,baseline)
proposal={'cell_id':CELL,'actor':ACTOR,'status':'draft','cases':cases,
    'sweep_specs':[{'sweep_id':'qualitative_original_review','target_law_id':LAW_ID,
        'judgment_refs':[{'phrase':phrase,'note':note} for phrase,note in phrases],
        'rationale':'Qualitative visibility, caution and yielding need original Native source and human pixel review before a frozen sweep is specified.',
        'status':'incomplete','missing_inputs':['Original Native source and view-opening pixel review',
            'Observable participant history and cautious-entry review']}],
    'semantic_status':'draft_incomplete_original_judgment_sweep'}
cases_ref=write('cases.json',proposal)
write('semantic-index.json',{'format':'worker-semantic-delivery',
    'assignment_id':ROOT.name,'stages':{'relevance_batch':batch_ref,
        'relevance':relevance_ref,'template':template_ref,
        'judgment_observables':judgment_refs,'bindings':binding_ref,'cases':cases_ref}})
