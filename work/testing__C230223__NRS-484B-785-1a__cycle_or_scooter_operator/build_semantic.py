"""Author exact-law draft canonical proposals without adopting any local job."""
import hashlib
import json
from pathlib import Path
from package_spec import ACTOR,AID,CELL,LAW,RECORDING
from scooter_785 import CASES


HERE=Path(__file__).resolve().parent
PROPOSALS=HERE/'proposals'
ROOT=HERE.parents[1]
LAW_TEXT=json.loads((ROOT/'inputs'/AID/'assignment.json').read_text())['law']['text']
TEMPLATE_ID=LAW+'@'+ACTOR
PARAMETERS=[
    ('ego_speed','subject_behavior','original measured mph over the full 900-frame capture','mph'),
    ('commanded_approach_speed','controller','requested physical speed target; not observed speed','m/s'),
    ('ordinance_context','world_setup','source-reviewed enacted ordinance or reviewed absence','source record'),
    ('scooter_qualification','world_setup','source-reviewed electric scooter definition characteristics','source record'),
    ('bicycle_lane_occupancy','world_setup','original scooter body in or outside designated bicycle lane','source record')]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(name,value):
    path=PROPOSALS/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    return {'path':str(path.relative_to(HERE)),'sha256':sha(path)}


def assignments(case):
    values={'ego_speed':None,
            'commanded_approach_speed':case.speed_mph*.44704,
            'ordinance_context':case.ordinance,
            'scooter_qualification':case.qualifies,
            'bicycle_lane_occupancy':case.in_lane}
    return {name:{'kind':kind,'value':values[name],'unit':unit}
            for name,kind,domain,unit in PARAMETERS}


def build():
    rel=put('relevance.json',{'cell_id':CELL,'actor':ACTOR,'status':'draft',
        'relevant_laws':[{'law_id':LAW,'quote':LAW_TEXT,
                          'applies_to':[ACTOR],'confidence':'medium'}],
        'borderline_excluded':[]})
    template=put('template.json',{'template_id':TEMPLATE_ID,'law_id':LAW,
        'actor':ACTOR,'status':'draft','quote':LAW_TEXT,
        'structure':{'law_id':LAW,
          'activation':{'condition':'Source-qualified electric scooter operated on a roadway, bicycle lane, path or route, subject to applicable ordinance.',
                        'numeric_conditions':[]},
          'obligation':{'description':'Observe actual operating speed not more than 15 mph where this state permission applies.',
                        'type':'must','numeric_conditions':[{'variable':'ego_speed','operator':'<=','value':15,'unit':'mph'}]},
          'exceptions':[{'source_clause':'Except as otherwise provided in an ordinance enacted pursuant to NRS 484A.469 [DEF-LVMC-11-40-185-A]',
                         'description':'Applicable ordinance text and its effect require official source review.',
                         'numeric_conditions':[]}],
          'timing':{'description':'Retain every actual original operating speed and body occupancy sample; do not infer speed from target.',
                    'numeric_conditions':[]},
          'judgment_calls_needed':[]},
        'parameter_refs':[{'name':name,'kind':kind,'range_or_domain':domain,'unit':unit}
                          for name,kind,domain,unit in PARAMETERS]})
    binding=put('bindings.json',{'cell_id':CELL,'actor':ACTOR,'status':'draft',
         'law_refs':[{'template_id':TEMPLATE_ID,'binding_kind':'direct'}],
         'context_refs':[],'fixed_parameters':[],
         'variable_parameters':[{'name':name,'kind':kind,'range_or_domain':domain,
                                 'unit':unit,'used_by_laws':[LAW]}
                                for name,kind,domain,unit in PARAMETERS]})
    baseline=CASES[0]
    planned=[{'case_id':AID+'__baseline','target_law_id':None,
              'target_type':'baseline','status':'draft',
              'rationale':'Neutral source-reviewed lane and scooter setup; no baseline recording selected.',
              'variable_assignments':assignments(baseline),
              'unresolved_judgment_calls':[],'recording_description':RECORDING}]
    for case in CASES:
        cid=AID+'__'+case.name
        if case.name in ('lane_14_5_mph','lane_15_mph','lane_15_5_mph'):
            group='speed_below_at_above'
            differences=['commanded_approach_speed','ego_speed']
            probe={'primary_variable':'ego_speed',
                   'comparison_or_standard':'NRS 484B.785(1)(a) not more than 15 mph',
                   'target_value_or_branch':case.speed_mph,
                   'threshold_ref':'obligation.numeric_conditions[0]',
                   'test_value':case.speed_mph,'operator':'<=','unit':'mph'}
            target_type='boundary_probe'
            epsilon={'value':.5,'unit':'mph',
                     'rationale':'Physical probe spacing about exact 15 mph statutory boundary; not a legal tolerance.'}
        elif case.name=='lane_14_5_ordinance':
            group='ordinance_context';differences=['ordinance_context']
            probe={'primary_variable':'ordinance_context',
                   'comparison_or_standard':'Source-reviewed ordinance exception and unresolved effect',
                   'target_value_or_branch':'reviewed_ordinance'}
            target_type='boundary_probe';epsilon=None
        elif case.name=='lane_14_5_nonqualifying':
            group='scooter_qualification';differences=['scooter_qualification']
            probe={'primary_variable':'scooter_qualification',
                   'comparison_or_standard':'Source electric scooter definition applicability',
                   'target_value_or_branch':False}
            target_type='boundary_probe';epsilon=None
        else:
            group='bicycle_lane_occupancy';differences=['bicycle_lane_occupancy']
            probe={'primary_variable':'bicycle_lane_occupancy',
                   'comparison_or_standard':'Official designated bicycle-lane occupancy',
                   'target_value_or_branch':False}
            target_type='boundary_probe';epsilon=None
        item={'case_id':cid,'target_law_id':LAW,'target_type':target_type,
              'status':'draft','rationale':'Source-bound exact bicycle-lane, scooter and speed branch; no physical or legal verdict claimed.',
              'paired_probe_id':group,'deliberate_differences':differences,
              'probe':probe,'variable_assignments':assignments(case),
              'unresolved_judgment_calls':[],'recording_description':RECORDING}
        if epsilon is not None:
            item['epsilon_used']=epsilon
        planned.append(item)
    cases=put('cases.json',{'cell_id':CELL,'actor':ACTOR,'status':'draft',
         'sweep_specs':[],'sweeps_expanded':True,'cases':planned})
    put('semantic-index.json',{'format':'worker-semantic-delivery',
        'assignment_id':AID,'status':'source_gated_draft',
        'stages':{'relevance_batch':rel,'relevance':rel,'template':template,
                  'judgment_observables':[],'bindings':binding,'cases':cases}})
    print('scooter semantic cases',len(planned)-1)


if __name__=='__main__':
    build()
