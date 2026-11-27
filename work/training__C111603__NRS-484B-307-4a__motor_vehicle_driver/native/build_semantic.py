"""Author draft canonical stages for the exact arrow and priority pairs."""

import hashlib
import json
import os
from pathlib import Path

from build_config import AID, build
from controller import SUFFIXES

ROOT=Path(__file__).resolve().parent.parent
REPO=ROOT.parents[1]
SCRATCH=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
PROPOSALS=ROOT/'proposals'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    stage=SCRATCH/('c111603-semantic-'+path.name+'.stage')
    stage.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    os.replace(stage,path)


def main():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    assignment=json.loads((REPO/'inputs'/AID/'assignment.json').read_text())
    quote=assignment['law']['text']
    law_id,cell_id,actor=(plan[key] for key in ('law_id','cell_id','actor'))
    template_id=law_id+'@'+actor
    common={'cell_id':cell_id,'actor':actor,'status':'draft'}
    relevance=dict(common,relevant_laws=[{'law_id':law_id,'quote':quote,
        'applies_to':[actor],'relevance_type':'specific_match','confidence':'high',
        'notes':'Frozen intersection/turn/other_vehicle cell; arrow and lawful priority require original source review.'}],
        borderline_excluded=[])
    put(PROPOSALS/'relevance-batch.json',relevance)
    put(PROPOSALS/'relevance.json',relevance)
    judgments=[
        {'phrase':'green turn arrow alone facing the driver',
         'note':'Raw Native Green cannot establish arrow-only pixels or that the head governs this approach.'},
        {'phrase':'pedestrians lawfully within the adjacent crosswalk',
         'note':'Original occupancy and independent permission/source review; position alone is insufficient.'},
        {'phrase':'other traffic lawfully using the intersection',
         'note':'Original other-vehicle trajectory and independent signal/priority review; position alone is insufficient.'},
        {'phrase':'yield the right-of-way',
         'note':'Original temporal and causal review is needed; a moving-overlap proxy is not a verdict.'},
    ]
    template={'template_id':template_id,'law_id':law_id,'actor':actor,
        'status':'draft','quote':quote,
        'structure':{'law_id':law_id,
            'activation':{'condition':'The subject faces a green turn arrow alone and proceeds into the intersection.','numeric_conditions':[]},
            'obligation':{'type':'must','description':'Proceed only in the arrow direction while illuminated, yielding right-of-way to lawful adjacent-crosswalk pedestrians and lawful intersection traffic.','numeric_conditions':[]},
            'exceptions':[],
            'timing':{'description':'Arrow illumination is frame-varying; priority applies while lawful participants use the crossing/intersection.','numeric_conditions':[]},
            'judgment_calls_needed':judgments},'parameter_refs':[]}
    put(PROPOSALS/'template.json',template)
    judgment_paths=[]
    terms=('dev.governs','ru.pedestrian','drv.in_intersection','drv.yields_to')
    for i,judgment in enumerate(judgments):
        value={'template_id':template_id,**judgment,'status':'draft',
            'observable_requirements':{'observables':[{
                'name':terms[i],'unit':'structured',
                'description':'Original time-joined Native actor, signal and four-camera sources'}],
                'context_inputs':[],
                'sweep_dimensions':[{'name':'probe_variant_code','unit':'configuration_index',
                    'description':'Finite physical configuration index, not a legal cutoff'}],
                'landmarks':[],
                'recording_needs':[{'name':'signal_native_and_pixels','unit':'structured',
                    'description':'Retain original signal and pixel provenance; independent review required'}],
                'limitations':['Requested arrow or overlap cannot establish this legal phrase.']}}
        path=PROPOSALS/('judgment-'+str(i)+'.json');put(path,value);judgment_paths.append(path)
    variables=[
        {'name':'probe_variant_code','kind':'controller',
         'range_or_domain':'0 through 7 finite exact physical configuration indices',
         'used_by_laws':[law_id]},
        {'name':'turn_route','kind':'controller',
         'range_or_domain':'indicated or contrary measured route','used_by_laws':[law_id]},
        {'name':'entry_signal_phase','kind':'world_setup',
         'range_or_domain':'observed lit or expired interval','used_by_laws':[law_id]},
        {'name':'participant_pause_request','kind':'controller',
         'range_or_domain':'pause or continue while source participant occupies conflict','used_by_laws':[law_id]},
        {'name':'observed_governance_and_lawfulness','kind':'subject_behavior',
         'range_or_domain':'original review or unresolved','used_by_laws':[law_id]},
    ]
    binding=dict(common,established_contexts=[{'name':'intersection_turn_other_vehicle',
        'source':'Frozen C111603 cell; governing head and lawful participant status require original review.'}],
        law_refs=[{'template_id':template_id,'binding_kind':'direct'}],
        context_refs=[],fixed_parameters=[],variable_parameters=variables)
    put(PROPOSALS/'bindings.json',binding)
    recording=build(SUFFIXES[0])['recording_description']
    baseline=dict(common,case_id=AID+'__baseline',target_law_id=None,
        target_type='baseline',rationale='Unselected neutral definition, no original capture.',
        variable_assignments={
            'probe_variant_code':{'kind':'controller','value':None,'unit':'configuration_index'},
            'turn_route':{'kind':'controller','value':'neutral','unit':'categorical'},
            'entry_signal_phase':{'kind':'world_setup','value':'neutral','unit':'categorical'},
            'participant_pause_request':{'kind':'controller','value':'neutral','unit':'categorical'},
            'observed_governance_and_lawfulness':{'kind':'subject_behavior','value':None,'unit':'structured'}},
        unresolved_judgment_calls=[],recording_description=recording)
    cases=[baseline]
    sweep_id='c111603-green-arrow-source-grid'
    for ordinal,source in enumerate(plan['cases']):
        suffix=source['case_id'].rsplit('__',1)[-1]
        route='contrary_turn' if suffix=='direction_contrary' else 'indicated_turn'
        phase='expired' if suffix=='arrow_expired' else 'lit'
        pause='pause' if suffix in ('pedestrian_yield','traffic_yield') else 'continue'
        cases.append(dict(common,case_id=source['case_id'],target_law_id=law_id,
            target_type=source['target_type'],
            rationale=source['physical_target']+'; original governance, lawfulness and yielding remain unverified.',
            paired_probe_id='green_arrow_source_'+suffix,
            deliberate_differences=['probe_variant_code'],
            probe={'primary_variable':'probe_variant_code',
                'comparison_or_standard':'fixed-source exact pair; no invented legal threshold',
                'target_value_or_branch':suffix},
            variable_assignments={
                'probe_variant_code':{'kind':'controller','value':float(ordinal),'unit':'configuration_index'},
                'turn_route':{'kind':'controller','value':route,'unit':'categorical'},
                'entry_signal_phase':{'kind':'world_setup','value':phase,'unit':'categorical'},
                'participant_pause_request':{'kind':'controller','value':pause,'unit':'categorical'},
                'observed_governance_and_lawfulness':{'kind':'subject_behavior','value':None,'unit':'structured'}},
            unresolved_judgment_calls=[j['phrase'] for j in judgments],
            deterministic_branch={'source_clause':quote,
                'judgment_context':[{'phrase':j['phrase'],'status':'fixed_assumption',
                    'reason':j['note'],'world_setup_refs':['entry_signal_phase']} for j in judgments]},
            sweep_id=sweep_id,sweep_point={'probe_variant_code':float(ordinal)},
            recording_description=recording))
    spec={'sweep_id':sweep_id,'target_law_id':law_id,'judgment_refs':judgments,
        'rationale':'Eight exact source configurations cover direction, illumination and both lawful-priority alternatives without legal thresholds.',
        'status':'complete','mode':'one_dimensional','landmarks':[],
        'axes':[{'variable':'probe_variant_code','observable':'probe_variant_code',
            'unit':'configuration_index','min':0,'max':7,'spacing':1,
            'range_rationale':'Eight exact selected physical configurations; index is identity only.',
            'spacing_rationale':'Unit step enumerates eight authored constructions, not statutory spacing.',
            'feasibility_evidence':'Eight inline Native bundles and offline CPU checks.',
            'measurement':{'method':'original configuration identity and source review',
                'time_window':'600 frames','statistic':'last'}}],
        'recording_description':recording}
    spec['spec_version']=hashlib.sha256(json.dumps(spec,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    spec['planned_case_count']=len(SUFFIXES)
    spec['selection_order']=[case['case_id'] for case in cases[1:]]
    for case in cases[1:]:case['sweep_spec_version']=spec['spec_version']
    put(PROPOSALS/'cases.json',dict(common,sweeps_expanded=True,sweep_specs=[spec],cases=cases))
    paths={stage:PROPOSALS/name for stage,name in (
        ('relevance_batch','relevance-batch.json'),('relevance','relevance.json'),
        ('template','template.json'),('bindings','bindings.json'),('cases','cases.json'))}
    refs={stage:{'path':str(path.relative_to(ROOT)),'sha256':sha(path)} for stage,path in paths.items()}
    refs['judgment_observables']=[{'path':str(path.relative_to(ROOT)),'sha256':sha(path)} for path in judgment_paths]
    put(PROPOSALS/'semantic-index.json',{'format':'worker-semantic-delivery',
        'assignment_id':AID,'stages':refs})
    print(json.dumps({'selected_cases':len(SUFFIXES),
                      'semantic_index_sha256':sha(PROPOSALS/'semantic-index.json')}))


if __name__=='__main__':
    main()
