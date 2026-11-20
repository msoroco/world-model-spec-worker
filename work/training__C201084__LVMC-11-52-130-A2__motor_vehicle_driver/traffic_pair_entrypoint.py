"""Exact optional-lead pair CPU bundle entrypoint and Native handoff."""
import argparse
import json
import os
import shutil
from pathlib import Path

from fire_lane_survey import CAMERAS
from native_capture import CAMERA_SPECS

HERE=Path(__file__).resolve().parent
ASSIGNMENT='training__C201084__LVMC-11-52-130-A2__motor_vehicle_driver'
MODES=('near_lead','absent_lead')
TUNINGS={
    'near_lead': {
        'primary': {},
        'fallback1': {'lead_stop_gap_m':8.0},
        'fallback2': {'lead_deceleration_mps2':2.0},
        'fallback3': {'cruise_mps':3.0}},
    'absent_lead': {
        'primary': {},
        'fallback1': {'destination_deceleration_mps2':3.0},
        'fallback2': {'cruise_mps':3.0},
        'fallback3': {'stop_radius_m':1.2}},
}


def check():
    config=json.loads((HERE/'config.json').read_text())
    mode=config.get('case_suffix')
    if mode not in MODES or config.get('case_id')!=ASSIGNMENT+'__'+mode or \
            config.get('selected_case_id')!=config.get('case_id') or \
            config.get('candidate_id') not in TUNINGS[mode] or \
            config.get('traffic_pair_controller_tuning',{})!=TUNINGS[mode][config.get('candidate_id')] or \
            config.get('law_id')!='LVMC-11-52-130-A2' or \
            config.get('cell_id')!='C201084' or \
            config.get('actor')!='motor_vehicle_driver' or \
            (config.get('rate_hz'),config.get('frames'),config.get('duration_s'))!=(20,600,30):
        raise ValueError('Exact traffic-pair identity or clock differs')
    pair=config.get('traffic_pair')
    if not isinstance(pair,dict) or pair.get('destination_xy_m')!=[30,1] or \
            pair.get('lead_present') is not (mode=='near_lead') or \
            pair.get('statutory_necessity_verified') is not False:
        raise ValueError('Exact traffic-pair construction differs')
    cameras=config.get('cameras')
    if not isinstance(cameras,list) or \
            [row.get('name') for row in cameras]!=list(CAMERAS) or \
            [(row.get('width'),row.get('height')) for row in cameras]!=\
            [(spec[1],spec[2]) for spec in CAMERA_SPECS]:
        raise ValueError('Original source-camera contract differs')
    channels=config.get('recording_description',{}).get('channels',[])
    if [row.get('name') for row in channels]!=[
            'ego_pose','ego_speed','vehicle_stops_in_posted_fire_lane',
            'lead_traffic_presence'] or \
            config.get('physical_acceptance_claimed') is not False or \
            config.get('legal_verdict') is not None:
        raise ValueError('Traffic-pair observation or no-verdict contract differs')
    return {'case_id':config['case_id'],'mode':mode,
            'candidate_id':config['candidate_id'],
            'controller_tuning':config.get('traffic_pair_controller_tuning',{}),
            'frames':600,
            'source_cameras':list(CAMERAS),'physical_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--survey',type=Path)
    parser.add_argument('--attempt',type=Path)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    checked=check()
    if args.check:
        print(json.dumps(checked,sort_keys=True))
        return
    survey_path=args.survey or (Path(os.environ['CARLA_SURVEY'])
                                if os.environ.get('CARLA_SURVEY') else None)
    attempt=args.output_dir or args.attempt
    if survey_path is None or attempt is None:
        parser.error('Supply CARLA_SURVEY or --survey, and --output-dir')
    import carla
    from traffic_pair_runner import run
    from traffic_pair_finalize import finalize
    client=carla.Client(args.host,args.port)
    client.set_timeout(180)
    survey=json.loads(survey_path.read_text())
    mode=checked['mode']
    receipt=run(client,carla,survey,mode,attempt,
                controller_tuning=checked['controller_tuning'])
    for name in ('config.json','construction.json','candidate-selection.json'):
        source,target=HERE/name,attempt/name
        if source.is_file() and source.resolve()!=target.resolve():
            shutil.copyfile(source,target)
    analysis=finalize(attempt,attempt/'analysis-report.json')
    from scenario_pipeline.worker_exchange.native_output import seal_capture
    seal_capture(attempt,frames=receipt['capture']['source_frames'],
                 restoration={'restored':receipt['capture']['restoration_verified']},
                 errors=[],encoder_exit_codes={name:0 for name in CAMERAS},
                 context={'survey_map_name':survey['map_name'],
                          'case_id':checked['case_id']})
    print(json.dumps({'capture':receipt,'analysis_report':
                      str(attempt/'analysis-report.json'),
                      'analysis_complete':analysis['analysis_complete'],
                      'physical_acceptance_claimed':False},sort_keys=True))


if __name__=='__main__':
    main()
