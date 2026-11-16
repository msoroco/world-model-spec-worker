"""Author the six value-free semantic stages for the right-side-pass pair."""
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from batch_pipeline.store import digest

assignment=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
plan=json.loads((ROOT/'case-plan.json').read_text())
source=json.loads((ROOT/'proposals/cases.json').read_text())
law=assignment['law'];cell=assignment['cell'];actor=assignment['actor']
law_id=law['id'];template_id=law_id+'@'+actor
phrase='conditions permitting such movement in safety'
note='Qualitative safety of the complete right-side passing movement; no numeric legal cutoff.'
recording=source['cases'][0]['recording_description']
proposals=ROOT/'proposals';proposals.mkdir(exist_ok=True)


def write(name,value):
    path=proposals/name
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    return {'path':'proposals/'+name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


relevance={'cell_id':cell['cell_id'],'actor':actor,'status':'draft',
    'relevant_laws':[{'law_id':law_id,'quote':law['text'],'applies_to':[actor],
        'relevance_type':'specific_match','confidence':'high',
        'notes':'The frozen one-way overtaking-right cell can stage the exact right-side pass; safety remains a judgment for later review.'}],
    'borderline_excluded':[]}
relevance_batch=write('relevance_batch.json',relevance)
relevance_ref=write('relevance.json',relevance)

template={'template_id':template_id,'law_id':law_id,'actor':actor,
    'status':'draft','quote':law['text'],
    'structure':{'activation':{'condition':'The driver overtakes and passes another vehicle upon the right.',
                                'source_clause':'overtake and pass another vehicle upon the right',
                                'numeric_conditions':[]},
                 'obligation':{'type':'must',
                    'description':'A right-side passing movement must occur only under conditions permitting such movement in safety.',
                    'source_clause':'only under conditions permitting such movement in safety',
                    'numeric_conditions':[]},
                 'exceptions':[],
                 'timing':{'description':'Evaluate conditions during the entire overtaking and passing movement.',
                           'numeric_conditions':[]},
                 'judgment_calls_needed':[{'phrase':phrase,'note':note}]},
    'parameter_refs':[]}
template_ref=write('template.json',template)

judgment={'template_id':template_id,'phrase':phrase,'note':note,'status':'draft',
    'observable_requirements':{
        'observables':[
            {'name':'ego_pose','unit':'structured','description':'Frame-joined original ego body and heading over the entire pass.'},
            {'name':'ego_speed','unit':'m/s','description':'Original measured ego speed, distinct from commanded speed.'},
            {'name':'right_side_pass_lateral_clearance','unit':'m',
             'description':'Observed body-to-body lateral surface gap during right-side overlap.'},
            {'name':'four_source_views','unit':'video',
             'description':'Synchronized overview, approach, corner and driver camera source frames.'}],
        'context_inputs':[{'name':'right_pass_map_readback','unit':'structured',
            'description':'Source-hashed native road and lane readback.'}],
        'sweep_dimensions':[{'name':'right_side_pass_lateral_clearance','unit':'m',
            'description':'Physical clearance coverage, without a legal safety threshold.'}],
        'landmarks':[],
        'recording_needs':[
            {'name':'ego_pose','unit':'structured','description':'Original ego body pose history.'},
            {'name':'ego_speed','unit':'m/s','description':'Original ego speed history.'},
            {'name':'right_side_pass_lateral_clearance','unit':'m','description':'Body gap from retained actor vertices.'},
            {'name':'four_source_views','unit':'video','description':'All four named source-camera videos.'}],
        'limitations':['These observations do not settle whether the movement was permitted in safety. Original motion and pixels require independent review.']}}
judgment_ref=write('judgment_observables_safety.json',judgment)

parameters=[
    ('road_and_actors','world_setup','one-way two-lane road, ego and lead vehicle'),
    ('commanded_lateral_apex','controller','two physically distinct right-lane apex requests in m'),
    ('commanded_ego_speed','controller','8 m/s primary requested speed; fallback policy may change it'),
    ('commanded_lead_speed','controller','4 m/s primary requested lead speed; fallback policy may change it'),
    ('ego_speed','subject_behavior','original measured ego speed in m/s'),
    ('lead_speed','subject_behavior','original measured lead speed in m/s'),
    ('right_side_pass_lateral_clearance','subject_behavior',
     'source-derived measured body gap during right-side longitudinal overlap in m')]
bindings={'cell_id':cell['cell_id'],'actor':actor,'status':'draft',
    'established_contexts':[{'name':'right_pass_layout',
        'source':'frozen one_way_multilane/overtake_right/other_vehicle catalog cell'}],
    'law_refs':[{'template_id':template_id,'binding_kind':'direct'}],
    'context_refs':[], 'fixed_parameters':[],
    'variable_parameters':[{'name':name,'kind':kind,'range_or_domain':domain,
        'used_by_laws':[law_id]} for name,kind,domain in parameters]}
bindings_ref=write('bindings.json',bindings)

def assignments(apex):
    values={'road_and_actors':'authored two-lane one-way road, ego and lead Tesla',
            'commanded_lateral_apex':apex,'commanded_ego_speed':8.0,
            'commanded_lead_speed':4.0,'ego_speed':None,'lead_speed':None,
            'right_side_pass_lateral_clearance':None}
    kinds={name:kind for name,kind,_ in parameters}
    return {name:{'kind':kinds[name],'value':value,
                  **({'unit':'m' if name=='commanded_lateral_apex' else 'm/s'}
                     if name in ('commanded_lateral_apex','commanded_ego_speed','commanded_lead_speed') else {})}
            for name,value in values.items()}

sweep_id=ROOT.name+'__clearance_sweep'
spec={'sweep_id':sweep_id,'target_law_id':law_id,
    'judgment_refs':[{'phrase':phrase,'note':note}],
    'rationale':'Fixed physical clearance coverage of one right-side pass; no legal safety cutoff.',
    'status':'complete','mode':'one_dimensional',
    'axes':[{'variable':'commanded_lateral_apex',
             'observable':'right_side_pass_lateral_clearance','unit':'m',
             'min':-5.5,'max':-4.8,'spacing':0.7,
             'range_rationale':'Two authored apex requests lie within the two 3.5 m rightward driving lanes and preserve a positive requested body gap.',
             'spacing_rationale':'0.7 m separates the selected body-gap probes while keeping one geometry and lead schedule.',
             'feasibility_evidence':'Authored 300 m two-lane OpenDRIVE road and source-bound 240-frame requested tracks; original motion unverified.',
             'measurement':{'method':'source-derived actor body surface gap during longitudinal overlap',
                            'time_window':'12 s complete pass','statistic':'min'}}],
    'landmarks':[], 'variable_assignments':assignments(-5.5),
    'recording_description':copy.deepcopy(recording)}
spec['spec_version']=digest(spec)
spec['planned_case_count']=2
spec['selection_order']=[ROOT.name+'__reference',ROOT.name+'__contrast']
cases=[]
baseline={'case_id':ROOT.name+'__baseline','target_law_id':None,
          'target_type':'baseline','rationale':'Shared authored right-pass setup; no baseline recording selected.',
          'variable_assignments':assignments(-5.5),
          'recording_description':copy.deepcopy(recording),
          'unresolved_judgment_calls':[phrase]}
cases.append(baseline)
for witness,apex in (('reference',-5.5),('contrast',-4.8)):
    item={'case_id':ROOT.name+'__'+witness,'target_law_id':law_id,
        'target_type':'judgment_sweep',
        'rationale':'Physical right-side body clearance '+witness+'; safety judgment unresolved.',
        'paired_probe_id':sweep_id,'deliberate_differences':['commanded_lateral_apex'],
        'probe':{'primary_variable':'commanded_lateral_apex',
            'comparison_or_standard':'physical coverage; legal safety unresolved',
            'target_value_or_branch':{'commanded_lateral_apex':apex}},
        'sweep_id':sweep_id,'sweep_spec_version':spec['spec_version'],
        'sweep_point':{'commanded_lateral_apex':apex},
        'variable_assignments':assignments(apex),
        'recording_description':copy.deepcopy(recording),
        'unresolved_judgment_calls':[phrase]}
    cases.append(item)
canonical={'cell_id':cell['cell_id'],'actor':actor,'status':'draft',
    'sweep_specs':[spec],'sweeps_expanded':True,'cases':cases}
cases_ref=write('canonical-cases.json',canonical)
index={'format':'worker-semantic-delivery','assignment_id':ROOT.name,
       'stages':{'relevance_batch':relevance_batch,'relevance':relevance_ref,
                 'template':template_ref,'judgment_observables':[judgment_ref],
                 'bindings':bindings_ref,'cases':cases_ref}}
write('semantic-index.json',index)
print(json.dumps({'stages':6,'selected_cases':2,'index_sha256':hashlib.sha256((proposals/'semantic-index.json').read_bytes()).hexdigest()}))
