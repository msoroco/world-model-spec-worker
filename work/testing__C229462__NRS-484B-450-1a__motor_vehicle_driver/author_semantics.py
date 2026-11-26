"""Author canonical source-gated motor-vehicle sidewalk semantic proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sidewalk_case import CASES

ROOT=Path(__file__).resolve().parent
AID=ROOT.name
LAW='NRS-484B-450-1a'
CELL='C229462'
ACTOR='motor_vehicle_driver'
TEXT=('A person shall not stop, stand or park a vehicle, except when necessary to avoid '
      'conflict with other traffic or in compliance with law or the directions of a police '
      'officer or official traffic-control device, in any of the following places: Except as '
      'otherwise provided in subsection 3, on a sidewalk. A person may park a bicycle, an '
      'electric bicycle or an electric scooter on a sidewalk provided that the bicycle, electric '
      'bicycle or electric scooter does not impede the normal and reasonable movement of '
      'pedestrians on the sidewalk.')
CHANNELS=('site_source','sidewalk_polygon','vehicle_body_history','ego_speed_history',
          'activity_history','exception_context','conflict_motion','camera_frame_map')
RECORDING={
    'channels':[{'name':name,'unit':'structured record','sampling_rate_hz':20,
                 'method':'Original Native frame acquisition and saved-only extraction',
                 'time_window':'road approach through terminal parking activity',
                 'reference_frame':'original frame/time and CARLA world',
                 'uncertainty':'20 Hz and vehicle body geometry sampling'} for name in CHANNELS],
    'context_inputs':[{'name':name,'unit':'source packet',
                       'method':'Reviewed original highway/sidewalk and exception source binding'}
                      for name in ('jurisdiction','highway_status','pedestrian_use','parking_purpose',
                                   'traffic_conflict_necessity','law_compliance','officer_direction',
                                   'official_device_direction','subsection_3')],
    'limitations':['Physical body overlap does not establish the statutory sidewalk or exceptions.',
                   'The bicycle/electric bicycle/electric scooter allowance does not classify the selected motor vehicle.']}
PARAMETERS=(('requested_relation','world_setup','overlap, touch or separate'),
            ('traffic_context','world_setup','absent or unresolved'))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main():
    p=ROOT/'proposals'
    relevance={'cell_id':CELL,'actor':ACTOR,'status':'draft',
               'relevant_laws':[{'law_id':LAW,'quote':TEXT,'applies_to':[ACTOR],
                                 'relevance_type':'direct sidewalk stopping/standing/parking restriction',
                                 'confidence':'high',
                                 'notes':'Actual sidewalk status, motor vehicle action and each exception remain source-gated.'}],
               'borderline_excluded':[]}
    write(p/'relevance.json',relevance);write(p/'relevance_batch.json',relevance)
    template={'template_id':LAW+'@'+ACTOR,'law_id':LAW,'actor':ACTOR,'quote':TEXT,
              'structure':{'law_id':LAW,
                           'activation':{'condition':'A motor vehicle stops, stands or parks at a legally defined sidewalk.',
                                         'numeric_conditions':[]},
                           'obligation':{'description':TEXT,'type':'must_not','numeric_conditions':[]},
                           'exceptions':[],
                           'timing':{'description':'Observe road approach, terminal vehicle body placement, activity and independent exception context.',
                                     'numeric_conditions':[]},
                           'judgment_calls_needed':[]},
              'parameter_refs':[{'name':n,'kind':k,'range_or_domain':d} for n,k,d in PARAMETERS]}
    write(p/'template.json',template)
    binding={'cell_id':CELL,'actor':ACTOR,'status':'draft',
             'established_contexts':['road','park maneuver','sidewalk'],
             'law_refs':[{'template_id':LAW+'@'+ACTOR,'binding_kind':'direct'}],
             'context_refs':[],'fixed_parameters':[],
             'variable_parameters':[{'name':n,'kind':k,'range_or_domain':d,'used_by_laws':[LAW]} for n,k,d in PARAMETERS]}
    write(p/'bindings.json',binding)
    cases={'cell_id':CELL,'actor':ACTOR,'status':'draft','cases':[],'sweep_specs':[]}
    cases['cases'].append({'case_id':AID+'__baseline','target_law_id':None,
                           'target_type':'baseline','rationale':'Off-sidewalk motor vehicle reference, not selected for capture.',
                           'variable_assignments':{'requested_relation':{'kind':'world_setup','value':'separate'},
                                                   'traffic_context':{'kind':'world_setup','value':'absent'}},
                           'unresolved_judgment_calls':[],'recording_description':RECORDING})
    for item in CASES:
        variables={'requested_relation':{'kind':'world_setup','value':item.relation},
                   'traffic_context':{'kind':'world_setup','value':item.traffic_context}}
        cases['cases'].append({'case_id':AID+'__'+item.case_id,'target_law_id':LAW,
                               'target_type':'boundary_probe' if item.traffic_context=='unresolved' else
                                             'compliant_attempt' if item.relation!='overlap' else 'violating_attempt',
                               'rationale':'Controlled motor-vehicle body/sidewalk and traffic-context probe; legal conclusions unresolved.',
                               'variable_assignments':variables,
                               'unresolved_judgment_calls':['legally defined sidewalk','actual parking conduct',
                                                            'traffic necessity','law/officer/device directions',
                                                            'subsection 3 scope'],
                               'recording_description':RECORDING,
                               'paired_probe_id':'sidewalk_body_and_necessity',
                               'deliberate_differences':list(variables),
                               'probe':{'primary_variable':'traffic_context' if item.traffic_context=='unresolved' else 'requested_relation',
                                        'comparison_or_standard':'original source-bound controlled contrast',
                                        'target_value_or_branch':{'relation':item.relation,
                                                                  'traffic_context':item.traffic_context}}})
    write(p/'cases.json',cases)
    refs={stage:{'path':'proposals/'+stage+'.json',
                 'sha256':hashlib.sha256((p/(stage+'.json')).read_bytes()).hexdigest()}
          for stage in ('relevance_batch','relevance','template','bindings','cases')}
    refs['judgment_observables']=[]
    write(p/'semantic-index.json',{'format':'worker-semantic-delivery','assignment_id':AID,'stages':refs})


if __name__=='__main__':
    main()
