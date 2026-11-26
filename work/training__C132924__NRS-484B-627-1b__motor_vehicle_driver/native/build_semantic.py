"""Author canonical exact-law proposals with explicit judgment observables."""

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
SCRATCH = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
PROPOSALS = ROOT/'proposals'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path,value):
    SCRATCH.mkdir(parents=True,exist_ok=True)
    path.parent.mkdir(parents=True,exist_ok=True)
    stage = SCRATCH/(path.name+'.semantic-stage')
    stage.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    os.replace(stage,path)


def main():
    plan = json.loads((ROOT/'case-plan.json').read_text())
    assignment = json.loads((REPO/'inputs'/plan['assignment_id']/'assignment.json').read_text())
    quote = assignment['law']['text']
    aid,law_id,cell_id,actor = (plan[key] for key in ('assignment_id','law_id','cell_id','actor'))
    template_id = law_id+'@'+actor
    common = {'cell_id':cell_id,'actor':actor,'status':'draft'}
    relevance = dict(common,relevant_laws=[{'law_id':law_id,'quote':quote,
        'applies_to':[actor],'relevance_type':'specific_match','confidence':'high',
        'notes':'Frozen multilane-roundabout travel cell and motor-vehicle driver scope.'}],
        borderline_excluded=[])
    put(PROPOSALS/'relevance-batch.json',relevance)
    put(PROPOSALS/'relevance.json',relevance)
    judgments = [
        {'phrase':'so slow as to impede the forward movement of traffic proceeding immediately behind',
         'note':'Original relative motion and independent impeding judgment; no numeric legal speed threshold.'},
        {'phrase':'necessary to pass other slowly moving vehicles',
         'note':'Original slower vehicle, causal necessity and pass duration need independent review.'}]
    template = {'template_id':template_id,'law_id':law_id,'actor':actor,
        'status':'draft','quote':quote,
        'structure':{'law_id':law_id,
            'activation':{'condition':'The subject is driving so slowly as to impede traffic immediately behind on a highway with two or more clearly marked same-direction lanes.','numeric_conditions':[]},
            'obligation':{'type':'must','description':'Drive in the extreme right-hand lane while the impeding condition lasts.','numeric_conditions':[]},
            'exceptions':[{'source_clause':'except when necessary to pass other slowly moving vehicles',
                           'condition':'When necessary to pass other slowly moving vehicles; only for the necessary passing interval.',
                           'numeric_conditions':[]}],
            'timing':{'description':'Continuous right-lane duty during impeding, with a source-observed necessary passing interval.','numeric_conditions':[]},
            'judgment_calls_needed':judgments},
        'parameter_refs':[]}
    put(PROPOSALS/'template.json',template)
    judgment_paths = []
    for i,judgment in enumerate(judgments):
        name = 'drv.queue_behind' if i==0 else 'drv.overtaking'
        value = {'template_id':template_id,**judgment,'status':'draft',
            'observable_requirements':{'observables':[{'name':name,'unit':'structured',
                'description':'Original time-joined Native ego, traffic, lane and motion sources relevant to this phrase'}],
                'context_inputs':[],'sweep_dimensions':[{'name':'probe_variant_code','unit':'configuration_index',
                    'description':'Finite physical configuration index only; no legal threshold or outcome'}],
                'landmarks':[],
                'recording_needs':[{'name':'native_lane_body_follower_and_pass','unit':'structured',
                    'description':'Retain original source and provenance; do not infer legal satisfaction'}],
                'limitations':['Synthetic speed ordering and requested passing do not establish the legal judgment.']}}
        path = PROPOSALS/('judgment-'+str(i)+'.json')
        put(path,value)
        judgment_paths.append(path)
    variables = [
        {'name':'impeding_vehicle_lane_position','kind':'controller',
         'range_or_domain':'extreme right or inner left requested lane, measured separately',
         'used_by_laws':[law_id]},
        {'name':'post_clearance_target_lane','kind':'controller',
         'range_or_domain':'return extreme right or linger inner left after observed pass clearance',
         'used_by_laws':[law_id]},
        {'name':'observed_impeding','kind':'subject_behavior',
         'range_or_domain':'original source review or unresolved',
         'used_by_laws':[law_id]},
        {'name':'impeding_context','kind':'world_setup',
         'range_or_domain':'stipulated active impeding target for controlled construction; independent outcome unresolved',
         'used_by_laws':[law_id]},
        {'name':'pass_context','kind':'world_setup',
         'range_or_domain':'stipulated necessary pass target or no pass; independent necessity unresolved',
         'used_by_laws':[law_id]},
        {'name':'probe_variant_code','kind':'controller',
         'range_or_domain':'0, 1, 2, 3 as finite physical configuration indices, not legal thresholds',
         'used_by_laws':[law_id]}]
    binding = dict(common,established_contexts=[{'name':'multilane_roundabout',
        'source':'Frozen C132924 catalog cell; actual marked lane and pass sources require Native review.'}],
        law_refs=[{'template_id':template_id,'binding_kind':'direct'}],
        context_refs=[],fixed_parameters=[],variable_parameters=variables)
    put(PROPOSALS/'bindings.json',binding)
    recording = json.loads((ROOT/'native/config.json').read_text())['recording_description']
    baseline = dict(common,case_id=aid+'__baseline',target_law_id=None,
        target_type='baseline',rationale='Unselected neutral definition with no original capture.',
        variable_assignments={
            'impeding_vehicle_lane_position':{'kind':'controller','value':'neutral','unit':'categorical'},
            'post_clearance_target_lane':{'kind':'controller','value':'neutral','unit':'categorical'},
            'observed_impeding':{'kind':'subject_behavior','value':None,'unit':'boolean'},
            'impeding_context':{'kind':'world_setup','value':'neutral','unit':'categorical'},
            'pass_context':{'kind':'world_setup','value':'neutral','unit':'categorical'},
            'probe_variant_code':{'kind':'controller','value':None,'unit':'configuration_index'}},
        unresolved_judgment_calls=[],recording_description=recording)
    cases = [baseline]
    sweep_id = 'c132924-roundabout-judgment-grid'
    codes = (0.0,3.0,1.0,2.0)
    for ordinal,source in enumerate(plan['cases']):
        case_id = source['case_id']
        suffix = case_id.rsplit('__',1)[-1]
        pass_case = suffix in ('necessary_pass','post_pass_linger')
        lane = 'extreme_right' if suffix=='probe_a' else 'inner_left'
        after = 'extreme_right' if suffix=='necessary_pass' else 'inner_left' if suffix=='post_pass_linger' else 'not_applicable'
        branch = {'source_clause':'drive in the extreme right-hand lane except when necessary to pass other slowly moving vehicles',
                  'judgment_context':[
                      {**judgments[0],'status':'fixed_assumption',
                       'reason':'The scenario targets immediately trailing traffic and slow ego motion; actual impeding remains for independent review.',
                       'world_setup_refs':['impeding_context']},
                      {**judgments[1],'status':'fixed_assumption' if pass_case else 'not_exercised',
                       'reason':'The pass pair stipulates a slower vehicle and tests interval duration; actual necessity remains for independent review.' if pass_case else 'No slower vehicle is constructed in the lane-position pair.',
                       'world_setup_refs':['pass_context'] if pass_case else []}]}
        cases.append(dict(common,case_id=case_id,target_law_id=law_id,
            target_type=source['target_type'],
            rationale=source['physical_target']+'; original impeding and passing judgments remain unverified.',
            paired_probe_id='roundabout_source_'+suffix,
            deliberate_differences=['probe_variant_code'],
            probe={'primary_variable':'probe_variant_code',
                   'comparison_or_standard':'fixed-source roundabout pair; no invented legal cutoff',
                   'target_value_or_branch':after if pass_case else lane},
            variable_assignments={
                'impeding_vehicle_lane_position':{'kind':'controller','value':lane,'unit':'categorical'},
                'post_clearance_target_lane':{'kind':'controller','value':after,'unit':'categorical'},
                'observed_impeding':{'kind':'subject_behavior','value':None,'unit':'boolean'},
                'impeding_context':{'kind':'world_setup','value':'stipulated_impeding_target','unit':'categorical'},
                'pass_context':{'kind':'world_setup','value':'stipulated_necessary_pass_target' if pass_case else 'no_pass','unit':'categorical'},
                'probe_variant_code':{'kind':'controller','value':codes[ordinal],'unit':'configuration_index'}},
            unresolved_judgment_calls=[j['phrase'] for j in judgments],deterministic_branch=branch,
            sweep_id=sweep_id,sweep_point={'probe_variant_code':codes[ordinal]},
            recording_description=recording))
    spec = {'sweep_id':sweep_id,'target_law_id':law_id,
            'judgment_refs':judgments,
            'rationale':'Four finite roundabout source configurations cover right/left duty and pass/return intervals without a legal numeric cutoff.',
            'status':'complete','mode':'one_dimensional','landmarks':[],
            'axes':[{'variable':'probe_variant_code','observable':'probe_variant_code',
                     'unit':'configuration_index','min':0,'max':3,'spacing':1,
                     'range_rationale':'Four selected exact configurations; index encodes configuration identity only.',
                     'spacing_rationale':'Unit index selects each of four authored configurations; no legal spacing implied.',
                     'feasibility_evidence':'Four selected inline Native constructions and offline checks.',
                     'measurement':{'method':'original configuration identifier and source review',
                                    'time_window':'600 frames','statistic':'last'}}],
            'recording_description':recording}
    spec['spec_version'] = hashlib.sha256(json.dumps(spec,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    spec['planned_case_count'] = 4
    spec['selection_order'] = [case['case_id'] for case in cases if case['target_type']!='baseline']
    for case in cases[1:]:
        case['sweep_spec_version'] = spec['spec_version']
    put(PROPOSALS/'cases.json',dict(common,sweeps_expanded=True,sweep_specs=[spec],cases=cases))
    paths = {stage:PROPOSALS/name for stage,name in (
        ('relevance_batch','relevance-batch.json'),('relevance','relevance.json'),
        ('template','template.json'),('bindings','bindings.json'),('cases','cases.json'))}
    refs = {stage:{'path':str(path.relative_to(ROOT)),'sha256':sha(path)} for stage,path in paths.items()}
    refs['judgment_observables'] = [{'path':str(path.relative_to(ROOT)),'sha256':sha(path)} for path in judgment_paths]
    put(PROPOSALS/'semantic-index.json',{'format':'worker-semantic-delivery',
        'assignment_id':aid,'stages':refs})
    print(json.dumps({'selected_cases':len(plan['cases']),
                      'semantic_index_sha256':sha(PROPOSALS/'semantic-index.json')}))


if __name__=='__main__':
    main()
