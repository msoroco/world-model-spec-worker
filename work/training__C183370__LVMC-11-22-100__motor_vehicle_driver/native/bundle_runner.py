"""Exact C183370 bundle entrypoint; CARLA is imported only for Native capture."""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'native'))
from pathing import repository_root
from recording_contract import ASSIGNMENT, description


def check():
    config=json.loads((HERE/'config.json').read_text())
    case=config.get('case_suffix')
    if (case not in ('reference','contrast') or
            config.get('case_id') != ASSIGNMENT+'__'+case or
            config.get('selected_case_id') != config['case_id'] or
            config.get('law_id') != 'LVMC-11-22-100' or
            config.get('cell_id') != 'C183370' or
            config.get('actor') != 'motor_vehicle_driver' or
            config.get('rate_hz') != 20 or
            type(config.get('frames')) is not int or config['frames'] < 600 or
            config.get('duration_s') != config['frames']/20 or
            config.get('recording_description') != description(config['frames'])):
        raise ValueError('Materialized C183370 case contract differs')
    repository_root(__file__)
    return {'case_id':config['case_id'],'frames':config['frames'],
            'original_carla_executed':False,'physical_acceptance_claimed':False}


def capture(output,host,port):
    config=json.loads((HERE/'config.json').read_text())
    check()
    survey_path=os.environ.get('C183370_SURVEY_JSON')
    if not survey_path:
        raise ValueError('Set C183370_SURVEY_JSON to the original surveyed scene')
    survey=json.loads(Path(survey_path).read_text())
    if survey.get('frames') != config['frames']:
        raise ValueError('Survey duration differs from exact case contract')
    import carla
    from capture import acquire
    client=carla.Client(host,port)
    client.set_timeout(10.0)
    return acquire(survey,config['case_suffix'],output,client,carla,
                   materialized=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.check:
        print(json.dumps(check(),sort_keys=True))
    else:
        if not args.output_dir:
            raise ValueError('Original capture requires --output-dir')
        capture(args.output_dir,args.host,args.port)


if __name__=='__main__':
    main()
