"""Case definitions for the two selected official-device lamp-setting cases."""
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main():
    cases=[]
    for suffix, lamp_on in (('controlled_1',True),('controlled_2',False)):
        case_id=HERE.name+'__'+suffix
        cases.append({'case_id':case_id, 'target_law_id':'NRS-484D-100-1',
                      'target_type':'delivery',
                      'rationale':'Official device directs lamp use; compare original lamp-state readback',
                      'variable_assignments':{
                          'frozen_cell':{'kind':'world_setup','value':'C179824 paved_road/travel/traffic_control_device'},
                          'device_instruction':{'kind':'world_setup','value':'HEADLAMPS ON'},
                          'lamp_setting_on':{'kind':'controller','value':lamp_on}},
                      'unresolved_judgment_calls':['official device authority',
                          'actual emitted light', 'class-specific equipment sufficiency'],
                      'recording_description':{
                          'channels':[{'name':'native_lamp_setting','unit':'boolean',
                                       'sampling_rate_hz':20,
                                       'method':'original CARLA light-state readback',
                                       'time_window':'600 frames',
                                       'reference_frame':'governed roadway',
                                       'uncertainty':'actual pixels and legal sufficiency unverified'},
                                      {'name':'device_and_highway_context','unit':'structured',
                                       'sampling_rate_hz':20,
                                       'method':'original roadway/sign survey plus independent review',
                                       'time_window':'600 frames',
                                       'reference_frame':'signed paved road',
                                       'uncertainty':'official authority and Nevada highway pending'}],
                          'context_inputs':[],
                          'limitations':['Source-shaped diagnostic is not physical evidence']}})
    value={'cell_id':'C179824','actor':'motor_vehicle_driver','status':'draft',
           'sweeps_expanded':True,'cases':cases,'sweep_specs':[]}
    target=HERE/'proposals/cases.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'passed':True,'cases':[item['case_id'] for item in cases]}))


if __name__=='__main__':
    main()
