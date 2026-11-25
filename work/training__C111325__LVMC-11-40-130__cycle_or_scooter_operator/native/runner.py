"""Selected exact-case Native bicycle capture entrypoint."""
import argparse
import json
from pathlib import Path
from bicycle_setup import plan
from live_capture import check as check_capture, execute

HERE = Path(__file__).resolve().parent


def check():
    config = json.loads((HERE/'config.json').read_text())
    request = plan(config['condition'], config['candidate_id'])
    if (config['case_id'] != config['selected_case_id'] or
            config['case']['case_id'] != config['case_id'] or
            config['cell_id'] != 'C111325' or config['law_id'] != 'LVMC-11-40-130' or
            config['actor'] != 'cycle_or_scooter_operator' or
            config['requested_speed_mps'] != request['requested_peak_speed_mps'] or
            config['start_xyz_m'] != list(request['start_xyz_m']) or
            config['rate_hz'] != 20 or config['duration_s'] != 30 or
            len(config['cameras']) != 4):
        raise ValueError('Selected bicycle construction changed')
    capture = check_capture()
    return {'passed': True, 'case_id': config['case_id'],
            'candidate_id': config['candidate_id'], 'frames': 600,
            'original_native_executed': False, 'capture': capture}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    result = check()
    if args.check:
        print(json.dumps(result))
    elif args.output_dir:
        config = json.loads((HERE/'config.json').read_text())
        print(json.dumps(execute(config['condition'], args.output_dir,
                                 args.host, args.port, config['candidate_id'])))
    else:
        parser.error('Supply --check or --output-dir')


if __name__ == '__main__':
    main()
