"""Exact reference roadway-stop bundle entrypoint for CPU and Native handoff."""
import argparse
import json
import os
from pathlib import Path

from candidate_tuning import TUNINGS, tuning
from native_channels import channels_for
from native_controller import camera_specs


HERE = Path(__file__).resolve().parent
ASSIGNMENT = 'training__C179480__NRS-484B-627-2__motor_vehicle_driver'
CASES = ('reference', 'contrast', 'safe_operation_stop')


def check():
    config = json.loads((HERE/'config.json').read_text())
    case = config.get('case_suffix')
    case_id = ASSIGNMENT + '__' + str(case)
    if (case not in CASES
            or config.get('case_id') != case_id
            or config.get('selected_case_id') != case_id
            or config.get('law_id') != 'NRS-484B-627-2'
            or config.get('cell_id') != 'C179480'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('rate_hz') != 20 or config.get('frames') != 600
            or config.get('duration_s') != 30):
        raise ValueError('Exact reference identity or 30-second clock differs')
    if [item['name'] for item in config['cameras']] != [
            spec['name'] for spec in camera_specs()]:
        raise ValueError('Original camera profile differs')
    if [(item['width'], item['height']) for item in config['cameras']] != [
            (spec['width'], spec['height']) for spec in camera_specs()]:
        raise ValueError('Original camera sizes differ')
    if [item['name'] for item in config['recording_description']['channels']] != list(
            channels_for(case)):
        raise ValueError('Recorded source channel contract differs')
    if config.get('candidate_id') not in TUNINGS:
        raise ValueError('Unknown selected physical-risk candidate')
    tuning(config['candidate_id'])
    return {'case_id': case_id, 'candidate_id': config['candidate_id'],
            'frames': 600, 'native_imported': False,
            'physical_acceptance_claimed': False}


def capture(output_dir, host, port):
    check()
    survey_name = os.environ.get('CARLA_SURVEY')
    if not survey_name:
        raise ValueError('Supply CARLA_SURVEY for the original map/lane readback')
    survey_path = Path(survey_name).resolve()
    survey = json.loads(survey_path.read_text())
    if survey.get('frames') != 600:
        raise ValueError('Survey must retain the exact 600-frame capture')
    import carla
    from native_runner import run
    from native_finalize import finalize
    client = carla.Client(host, port)
    client.set_timeout(20)
    config = json.loads((HERE/'config.json').read_text())
    receipt = run(client, carla, survey, output_dir, config['case_suffix'],
                  candidate=json.loads((HERE/'config.json').read_text())['candidate_id'])
    report = finalize(output_dir, Path(output_dir)/'analysis-report.json')
    return {'capture': receipt, 'finalizer': report,
            'survey_path': str(survey_path),
            'original_native_accepted': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(), sort_keys=True))
    else:
        if args.output_dir is None:
            parser.error('--output-dir is required')
        print(json.dumps(capture(args.output_dir,args.host,args.port),sort_keys=True))


if __name__ == '__main__':
    main()
