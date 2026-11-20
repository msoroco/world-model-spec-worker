"""Exact lead-conflict CPU bundle entrypoint and Native handoff."""
import argparse
import json
import os
import shutil
from pathlib import Path

from exception_capture import CAMERA_SPECS
from fire_lane_survey import CAMERAS


HERE = Path(__file__).resolve().parent
ASSIGNMENT = 'training__C201084__LVMC-11-52-130-A2__motor_vehicle_driver'
CASE = ASSIGNMENT+'__conflict'


def check():
    config = json.loads((HERE/'config.json').read_text())
    if (config.get('case_id') != CASE or
            config.get('selected_case_id') != CASE or
            config.get('case_suffix') != 'conflict' or
            config.get('law_id') != 'LVMC-11-52-130-A2' or
            config.get('cell_id') != 'C201084' or
            config.get('actor') != 'motor_vehicle_driver' or
            config.get('candidate_id') != 'primary' or
            config.get('rate_hz') != 20 or
            config.get('frames') != 600 or
            config.get('duration_s') != 30):
        raise ValueError('Exact lead-conflict identity or clock differs')
    cameras = config.get('cameras')
    if (not isinstance(cameras, list) or
            [item.get('name') for item in cameras] != list(CAMERAS) or
            [(item.get('width'), item.get('height')) for item in cameras] !=
            [(spec[1], spec[2]) for spec in CAMERA_SPECS]):
        raise ValueError('Original source-camera contract differs')
    channels = config.get('recording_description', {}).get('channels', [])
    if ([row.get('name') for row in channels] !=
            ['ego_pose', 'ego_speed', 'vehicle_stops_in_posted_fire_lane',
             'lead_traffic_relation'] or
            config.get('physical_acceptance_claimed') is not False or
            config.get('legal_verdict') is not None):
        raise ValueError('Conflict observation or no-verdict contract differs')
    return {'case_id': CASE, 'frames': 600, 'source_cameras': list(CAMERAS),
            'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--survey', type=Path)
    parser.add_argument('--attempt', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    checked = check()
    if args.check:
        print(json.dumps(checked, sort_keys=True))
        return
    survey_path = args.survey or (Path(os.environ['CARLA_SURVEY'])
                                  if os.environ.get('CARLA_SURVEY') else None)
    attempt = args.output_dir or args.attempt
    if survey_path is None or attempt is None:
        parser.error('Supply CARLA_SURVEY or --survey, and --output-dir')
    import carla
    from exception_runner import run
    from exception_finalize import finalize
    client = carla.Client(args.host, args.port)
    client.set_timeout(180)
    survey = json.loads(survey_path.read_text())
    receipt = run(client, carla, survey, attempt)
    for name in ('config.json', 'construction.json',
                 'candidate-selection.json'):
        source, target = HERE/name, attempt/name
        if source.is_file() and source.resolve() != target.resolve():
            shutil.copyfile(source, target)
    analysis = finalize(attempt, attempt/'analysis-report.json')
    from scenario_pipeline.worker_exchange.native_output import seal_capture
    seal_capture(attempt, frames=receipt['capture']['source_frames'],
                 restoration={'restored': receipt['capture']['restoration_verified']},
                 errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'survey_map_name': survey['map_name'],
                          'case_id': checked['case_id']})
    print(json.dumps({'capture': receipt, 'analysis_report':
                      str(attempt/'analysis-report.json'),
                      'analysis_complete': analysis['analysis_complete'],
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
