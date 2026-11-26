"""Author canonical exact driveway-sidewalk semantic proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from driveway_case import CASES

ROOT=Path(__file__).resolve().parent
AID=ROOT.name
LAW='LVMC-11-40-140'
CELL='C213645'
ACTOR='cycle_or_scooter_operator'
TEXT=('The operator of a bicycle, electric bicycle, or electric scooter within a business '
      'or residence district entering into or emerging from an alley, driveway or building '
      'shall stop such vehicle immediately prior to driving onto a sidewalk or onto the '
      'sidewalk area extending across any alleyway, driveway or building, yielding the '
      'right-of-way to any pedestrian as may be necessary to avoid collision.')
CHANNELS=('site_source','district_access_context','sidewalk_edge','cycle_speed_history',
          'edge_distance_history','pedestrian_motion','pedestrian_conflict','operator_yield',
          'camera_frame_map')
RECORDING={
    'channels':[{'name':name,'unit':'structured record','sampling_rate_hz':20,
                 'method':'Original Native frame acquisition and saved-only extraction',
                 'time_window':'driveway approach, pre-entry stop, sidewalk crossing and pedestrian passage',
                 'reference_frame':'original frame/time and CARLA world',
                 'uncertainty':'20 Hz sampled motion; no legal proximity cutoff'} for name in CHANNELS],
    'context_inputs':[{'name':name,'unit':'source packet',
                       'method':'Reviewed original municipal district, access, sidewalk and device source binding'}
                      for name in ('jurisdiction','district','district_frontage',
                                   'driveway_permission','vehicle_class','sidewalk_area',
                                   'pedestrian_conflict_region')],
    'limitations':['A sampled low speed is an engineering readback, not a legal complete-stop definition.',
                   'Immediate proximity, pedestrian priority and collision necessity require original review.']}
PARAMETERS=(('requested_stop','world_setup','true or false'),
            ('requested_pedestrian','world_setup','true or false'),
            ('requested_yield','world_setup','true or false'))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main():
    p=ROOT/'proposals'
    relevance={'cell_id':CELL,'actor':ACTOR,'status':'draft',
               'relevant_laws':[{'law_id':LAW,'quote':TEXT,'applies_to':[ACTOR],
                                 'relevance_type':'direct driveway sidewalk crossing duty',
                                 'confidence':'high',
                                 'notes':'Qualifying district, device, access, sidewalk and pedestrian necessity remain source-gated.'}],
               'borderline_excluded':[]}
    write(p/'relevance.json',relevance);write(p/'relevance_batch.json',relevance)
    template={'template_id':LAW+'@'+ACTOR,'law_id':LAW,'actor':ACTOR,'quote':TEXT,
              'structure':{'law_id':LAW,
                           'activation':{'condition':'Qualifying cycle or scooter operator in business or residence district enters or emerges from driveway onto sidewalk area.',
                                         'numeric_conditions':[]},
                           'obligation':{'description':TEXT,'type':'must','numeric_conditions':[]},
                           'exceptions':[],
                           'timing':{'description':'Immediately prior to sidewalk-area entry and yielding as needed to avoid collision.',
                                     'numeric_conditions':[]},
                           'judgment_calls_needed':[]},
              'parameter_refs':[{'name':n,'kind':k,'range_or_domain':d} for n,k,d in PARAMETERS]}
    write(p/'template.json',template)
    binding={'cell_id':CELL,'actor':ACTOR,'status':'draft',
             'established_contexts':['residence_district','enter_road','driveway_entrance'],
             'law_refs':[{'template_id':LAW+'@'+ACTOR,'binding_kind':'direct'}],
             'context_refs':[],'fixed_parameters':[],
             'variable_parameters':[{'name':n,'kind':k,'range_or_domain':d,'used_by_laws':[LAW]} for n,k,d in PARAMETERS]}
    write(p/'bindings.json',binding)
    cases={'cell_id':CELL,'actor':ACTOR,'status':'draft','cases':[],'sweep_specs':[]}
    cases['cases'].append({'case_id':AID+'__baseline','target_law_id':None,
                           'target_type':'baseline','rationale':'Driveway sidewalk crossing reference, not selected for capture.',
                           'variable_assignments':{'requested_stop':{'kind':'world_setup','value':True},
                                                   'requested_pedestrian':{'kind':'world_setup','value':False},
                                                   'requested_yield':{'kind':'world_setup','value':False}},
                           'unresolved_judgment_calls':[],'recording_description':RECORDING})
    for item in CASES:
        variables={'requested_stop':{'kind':'world_setup','value':item.stop},
                   'requested_pedestrian':{'kind':'world_setup','value':item.pedestrian},
                   'requested_yield':{'kind':'world_setup','value':item.yield_to_pedestrian}}
        cases['cases'].append({'case_id':AID+'__'+item.case_id,'target_law_id':LAW,
                               'target_type':'compliant_attempt' if item.stop and
                                             (not item.pedestrian or item.yield_to_pedestrian) else 'violating_attempt',
                               'rationale':'Controlled source-bound pre-entry stop, pedestrian conflict and yield probe; legal conclusions unresolved.',
                               'variable_assignments':variables,
                               'unresolved_judgment_calls':['qualifying district and driveway',
                                                            'complete stop immediately prior',
                                                            'pedestrian right-of-way and collision necessity'],
                               'recording_description':RECORDING,
                               'paired_probe_id':'driveway_stop_pedestrian_yield',
                               'deliberate_differences':list(variables),
                               'probe':{'primary_variable':'requested_stop' if not item.stop else
                                                           'requested_pedestrian' if not item.pedestrian else 'requested_yield',
                                        'comparison_or_standard':'original source-bound controlled contrast',
                                        'target_value_or_branch':{'stop':item.stop,'pedestrian':item.pedestrian,
                                                                  'yield':item.yield_to_pedestrian}}})
    write(p/'cases.json',cases)
    refs={stage:{'path':'proposals/'+stage+'.json',
                 'sha256':hashlib.sha256((p/(stage+'.json')).read_bytes()).hexdigest()}
          for stage in ('relevance_batch','relevance','template','bindings','cases')}
    refs['judgment_observables']=[]
    write(p/'semantic-index.json',{'format':'worker-semantic-delivery','assignment_id':AID,'stages':refs})


if __name__=='__main__':
    main()
