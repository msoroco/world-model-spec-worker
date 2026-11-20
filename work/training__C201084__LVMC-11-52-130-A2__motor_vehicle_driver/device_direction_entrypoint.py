"""Exact draft device-direction CPU bundle and Native handoff."""
import argparse
import json
import os
import shutil
from math import isfinite
from pathlib import Path

from fire_lane_survey import CAMERAS
from native_capture import CAMERA_SPECS

HERE=Path(__file__).resolve().parent
ASSIGNMENT='training__C201084__LVMC-11-52-130-A2__motor_vehicle_driver'
CASE=ASSIGNMENT+'__device_direction'


def check():
    config=json.loads((HERE/'config.json').read_text())
    if (config.get('case_id')!=CASE or
            config.get('selected_case_id')!=CASE or
            config.get('case_suffix')!='device_direction' or
            config.get('candidate_id') not in
            ('primary','fallback1','fallback2','fallback3') or
            config.get('law_id')!='LVMC-11-52-130-A2' or
            config.get('cell_id')!='C201084' or
            config.get('actor')!='motor_vehicle_driver' or
            (config.get('rate_hz'),config.get('frames'),
             config.get('duration_s'))!=(20,600,30)):
        raise ValueError('Exact device-direction identity or clock differs')
    cameras=config.get('cameras')
    if (not isinstance(cameras,list) or
            [row.get('name') for row in cameras]!=list(CAMERAS) or
            [(row.get('width'),row.get('height')) for row in cameras]!=
            [(row[1],row[2]) for row in CAMERA_SPECS]):
        raise ValueError('Original source-camera contract differs')
    if (config.get('physical_acceptance_claimed') is not False or
            config.get('legal_verdict') is not None or
            config.get('direction_applicability_verified') is not False or
            config.get('statutory_necessity_verified') is not False):
        raise ValueError('Device route cannot assert legal or physical completion')
    tuning=config.get('controller_tuning')
    allowed=('stop_radius_m','cruise_mps','deceleration_mps2',
             'following_brake_gap_m','following_cruise_throttle')
    if tuning is not None and (not isinstance(tuning,dict) or
            set(tuning)!=set(allowed) or
            any(type(tuning[key]) not in (int,float) or
                not isfinite(tuning[key]) or tuning[key]<=0
                for key in allowed) or tuning['following_cruise_throttle']>1):
        raise ValueError('Invalid device candidate controller tuning')
    if config['candidate_id']!='primary' and tuning is None:
        raise ValueError('Device fallback needs explicit controller tuning')
    return {'case_id':CASE,'candidate_id':config['candidate_id'],'frames':600,
            'source_cameras':list(CAMERAS),
            'physical_acceptance_claimed':False}


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
    from device_direction_runner import run
    from device_direction_finalize import finalize
    client=carla.Client(args.host,args.port)
    client.set_timeout(180)
    survey=json.loads(survey_path.read_text())
    config=json.loads((HERE/'config.json').read_text())
    receipt=run(client,carla,survey,attempt,
                controller_tuning=config.get('controller_tuning'))
    for name in ('config.json','construction.json','candidate-selection.json'):
        source,target=HERE/name,Path(attempt)/name
        if source.is_file() and source.resolve()!=target.resolve():
            shutil.copyfile(source,target)
    report=finalize(attempt,Path(attempt)/'analysis-report.json')
    from scenario_pipeline.worker_exchange.native_output import seal_capture
    seal_capture(attempt,frames=receipt['capture']['source_frames'],
                 restoration={'restored':receipt['capture']['restoration_verified']},
                 errors=[],encoder_exit_codes={name:0 for name in CAMERAS},
                 context={'survey_map_name':survey['map_name'],
                          'case_id':checked['case_id']})
    print(json.dumps({'capture':receipt,
                      'analysis_complete':report['analysis_complete'],
                      'physical_acceptance_claimed':False},sort_keys=True))


if __name__=='__main__':
    main()
