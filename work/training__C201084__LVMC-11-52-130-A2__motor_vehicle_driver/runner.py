"""Exact C201084 draft primary entrypoint for CPU and Native handoff."""
import argparse
import json
from pathlib import Path

from fire_lane_survey import CAMERAS
from native_capture import CAMERA_SPECS


HERE = Path(__file__).resolve().parent
ASSIGNMENT = 'training__C201084__LVMC-11-52-130-A2__motor_vehicle_driver'


def check():
    config = json.loads((HERE/'config.json').read_text())
    case = config.get('case_suffix')
    case_id = ASSIGNMENT+'__'+str(case)
    if (case not in ('reference', 'contrast') or
            config.get('case_id') != case_id or
            config.get('selected_case_id') != case_id or
            config.get('law_id') != 'LVMC-11-52-130-A2' or
            config.get('cell_id') != 'C201084' or
            config.get('actor') != 'motor_vehicle_driver' or
            config.get('candidate_id') != 'primary' or
            config.get('rate_hz') != 20 or
            config.get('frames') != 600 or
            config.get('duration_s') != 30):
        raise ValueError('Exact fire-lane primary identity or clock differs')
    cameras = config.get('cameras')
    if (not isinstance(cameras, list) or
            [item.get('name') for item in cameras] != list(CAMERAS) or
            [(item.get('width'), item.get('height')) for item in cameras] !=
            [(spec[1], spec[2]) for spec in CAMERA_SPECS]):
        raise ValueError('Original source-camera contract differs')
    if (config.get('physical_acceptance_claimed') is not False or
            config.get('legal_verdict') is not None):
        raise ValueError('CPU bundle cannot assert physical or legal completion')
    return {'case_id': case_id, 'frames': 600,
            'source_cameras': list(CAMERAS),
            'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--survey', type=Path)
    parser.add_argument('--attempt', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    checked = check()
    if args.check:
        print(json.dumps(checked, sort_keys=True))
        return
    if args.survey is None or args.attempt is None:
        parser.error('--survey and --attempt are required for Native acquisition')
    import carla
    from native_runner import run
    client = carla.Client(args.host, args.port)
    client.set_timeout(180)
    survey = json.loads(args.survey.read_text())
    print(json.dumps(run(client, carla, survey,
                         json.loads((HERE/'config.json').read_text())['case_suffix'],
                         args.attempt), sort_keys=True))


if __name__ == '__main__':
    main()
