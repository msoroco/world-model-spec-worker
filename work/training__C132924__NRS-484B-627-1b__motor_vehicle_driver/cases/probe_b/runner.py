"""Check an exact roundabout request on CPU or acquire original Native data."""

import argparse
import json
from pathlib import Path

from controller import SourceState, request

HERE = Path(__file__).resolve().parent
SUFFIXES = ('probe_a', 'probe_b', 'necessary_pass', 'post_pass_linger')


def check(config_path=None):
    config = json.loads(Path(config_path or HERE/'config.json').read_text())
    if (config.get('cell_id') != 'C132924' or
            config.get('law_id') != 'NRS-484B-627-1b' or
            config.get('actor') != 'motor_vehicle_driver' or
            config.get('frames') != 600 or config.get('rate_hz') != 20 or
            config.get('duration_s') != 30):
        raise ValueError('Exact frozen roundabout identity or duration differs')
    ids = [config['assignment_id']+'__'+suffix for suffix in SUFFIXES]
    if (config.get('supported_case_ids') != ids or
            config.get('selected_case_id') not in ids or
            config.get('case_id') != config['selected_case_id']):
        raise ValueError('Exact selected roundabout case differs')
    names = ('overview','approach','reference_corner','driver_reference')
    if tuple(config.get('camera_sources',())) != names:
        raise ValueError('Four original source cameras required')
    state = SourceState(3.0,14.5,2.5,8.0,2.0,False)
    phases = {suffix:request(suffix,state).phase for suffix in SUFFIXES}
    state = SourceState(3.0,11.5,2.5,8.0,2.0,True)
    phases['necessary_pass_after_clearance'] = request('necessary_pass',state).phase
    phases['post_pass_linger_after_clearance'] = request('post_pass_linger',state).phase
    if (phases['necessary_pass_after_clearance'] != 'return_after_pass' or
            phases['post_pass_linger_after_clearance'] != 'linger_after_pass'):
        raise ValueError('Statutory pass-duration controller branch missing')
    return {'case_id':config['case_id'],'exact_cases_checked':4,'frames':600,
            'rate_hz':20,'source_cameras_planned':4,'controller_phases':phases,
            'native_executed':False,'legal_verdict_claimed':False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--context-survey',type=Path)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args = parser.parse_args()
    checked = check()
    if args.check:
        print(json.dumps(checked,sort_keys=True))
        return
    if args.output_dir is None:
        raise ValueError('Fresh materialized Native output directory required')
    from capture import execute
    execute(json.loads((HERE/'config.json').read_text()),args.output_dir,
            args.host,args.port,args.context_survey)


if __name__ == '__main__':
    main()
