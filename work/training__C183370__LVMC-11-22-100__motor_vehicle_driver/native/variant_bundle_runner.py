"""Exact C183370 control-variant entrypoint; CARLA is Native-only."""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from pathing import repository_root
from variant_recording_contract import config as expected_config

KNOBS = {
    'primary': ({'speed_mps': 4.0, 'reach_m': 1.5, 'steer_divisor_deg': 40.0}, {}),
    'fallback1': ({'speed_mps': 3.0, 'reach_m': 1.5, 'steer_divisor_deg': 40.0}, {}),
    'fallback2': ({'speed_mps': 4.0, 'reach_m': 1.5, 'steer_divisor_deg': 40.0},
                  {'overview': {'offset_xyz_m': [-8.0, 0.0, 28.0], 'pitch_deg': -62.0}}),
    'fallback3': ({'speed_mps': 4.0, 'reach_m': 1.0, 'steer_divisor_deg': 32.0}, {}),
}


def check():
    config = json.loads((HERE / 'config.json').read_text())
    kind, route, candidate = (config.get(key) for key in
                              ('control_kind', 'case_suffix', 'candidate_id'))
    expected = expected_config(kind, route, config.get('frames'))
    if (candidate not in KNOBS or
            (config.get('controller_knobs'), config.get('camera_overrides')) != KNOBS[candidate] or
            any(config.get(key) != value for key, value in expected.items()) or
            config.get('selected_case_id') != expected['case_id'] or
            config.get('required_atoms') != [] or config.get('source_packets') != []):
        raise ValueError('Materialized variant case contract differs')
    repository_root(__file__)
    return {'case_id': expected['case_id'], 'frames': expected['frames'],
            'original_carla_executed': False, 'physical_acceptance_claimed': False}


def capture(output, host, port):
    config = json.loads((HERE / 'config.json').read_text())
    check()
    survey_path = os.environ.get('C183370_SURVEY_JSON')
    if not survey_path:
        raise ValueError('Set C183370_SURVEY_JSON to the original control-variant survey')
    survey = json.loads(Path(survey_path).read_text())
    if survey.get('control_kind') != config['control_kind'] or survey.get('frames') != config['frames']:
        raise ValueError('Survey route or duration differs from exact variant')
    import carla
    from variant_capture import acquire
    client = carla.Client(host, port)
    client.set_timeout(10.0)
    return acquire(survey, config['case_suffix'], output, client, carla)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(), sort_keys=True))
    else:
        if not args.output_dir:
            raise ValueError('Original variant capture requires --output-dir')
        capture(args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
