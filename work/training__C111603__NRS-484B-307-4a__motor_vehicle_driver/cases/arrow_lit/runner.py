"""CPU-check exact request or run source-driven Native acquisition later."""

import argparse
import json
from pathlib import Path

from build_config import AID, CAMERAS
from controller import Observation, SUFFIXES, request

HERE = Path(__file__).resolve().parent


def check(config_path=None):
    config = json.loads(Path(config_path or HERE / 'config.json').read_text())
    ids = [AID + '__' + suffix for suffix in SUFFIXES]
    if (config.get('assignment_id') != AID
            or config.get('law_id') != 'NRS-484B-307-4a'
            or config.get('cell_id') != 'C111603'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('frames') != 600 or config.get('rate_hz') != 20
            or config.get('duration_s') != 30
            or config.get('supported_case_ids') != ids
            or config.get('selected_case_id') not in ids
            or config.get('case_id') != config['selected_case_id']
            or config.get('camera_sources') != [c[0] for c in CAMERAS]):
        raise ValueError('Exact green-arrow identity, timing or cameras differ')
    state = Observation(120, True, True, True, True, 0.0)
    phases = {suffix: request(suffix, state).phase for suffix in SUFFIXES}
    if (phases['arrow_expired'] != 'wait_for_observed_arrow_end'
            or phases['pedestrian_yield'] != 'pause_for_observed_pedestrian'
            or phases['traffic_yield'] != 'pause_for_observed_traffic'):
        raise ValueError('Exact controller branch missing')
    return {'case_id': config['case_id'], 'exact_cases_checked': len(ids),
            'source_cameras_planned': len(CAMERAS), 'frames': 600,
            'rate_hz': 20, 'controller_phases': phases,
            'native_executed': False, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--context-survey', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    checked = check()
    if args.check:
        print(json.dumps(checked, sort_keys=True))
        return
    if args.output_dir is None:
        raise ValueError('Fresh original Native attempt output directory required')
    from capture import execute
    execute(json.loads((HERE / 'config.json').read_text()), args.output_dir,
            args.host, args.port, args.context_survey)


if __name__ == '__main__':
    main()
