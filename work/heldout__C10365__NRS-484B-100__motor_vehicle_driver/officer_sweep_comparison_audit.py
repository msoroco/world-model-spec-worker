"""Independent source-bound audit of the three fixed indication-window points."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PREFIX = 'heldout__C10365__NRS-484B-100__motor_vehicle_driver__stop_response_window_grid-'
ORDER = (0, 1, 2)
FRAMES = (30, 50, 40)
DIAGNOSTIC_FRAMES = (38034, 38038, 38036)


def audit(attempts):
    if len(attempts) != 3:
        raise ValueError('Three exact indication-window cases required')
    fixed = None
    measured = []
    for index, attempt in enumerate(map(Path, attempts)):
        def load(name):
            path = attempt / name
            if not path.is_file():
                raise ValueError('Missing required source: ' + name)
            return json.loads(path.read_text())

        config = load('config.json')
        context = load('officer_context.json')
        direction = load('officer_direction.json')
        motion = load('subject_motion.json')
        result = load('result.json')
        expected_case = PREFIX + f'{ORDER[index]:04d}'
        if config.get('selected_case_id') != expected_case or result.get('case_id') != expected_case:
            raise ValueError('Comparison case identity changed')
        if config.get('direction_frame') != FRAMES[index] or direction.get('frame') != DIAGNOSTIC_FRAMES[index]:
            raise ValueError('Indication timing differs from frozen sweep point')
        if direction.get('command') != 'stop' or context.get('officer_role') != 'police_officer':
            raise ValueError('Fixed stop indication or officer changed')
        if not motion.get('frames') or len(motion['frames']) < 3:
            raise ValueError('Original subject motion missing')
        conditions = (config.get('law_id'), config.get('cell_id'), config.get('actor'),
                      config.get('rate_hz'), config.get('duration_s'), config.get('cameras'),
                      config.get('case', {}).get('intended_observed_response'),
                      context.get('officer_id'), context.get('subject_id'),
                      tuple((r.get('frame'), r.get('speed_mps')) for r in motion['frames']))
        if fixed is None:
            fixed = conditions
        elif conditions != fixed:
            raise ValueError('Fixed actor, controller, camera or motion conditions changed')
        measured.append({'case_id': expected_case, 'direction_frame': direction['frame'],
                         'minimum_post_speed_mps': result['measured_values']['officer_response']['min_post_speed_mps']})
    if len({row['direction_frame'] for row in measured}) != 3:
        raise ValueError('Deliberate indication-window difference absent')
    return {'format': 'worker-officer-sweep-comparison-audit', 'comparison_complete': True,
            'fixed_conditions_checked': ['law', 'cell', 'actor', 'rate', 'duration', 'cameras',
                                         'response_controller', 'officer', 'subject', 'motion'],
            'deliberate_difference': 'timed officer indication frame', 'points': measured,
            'legal_conclusion': None, 'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempts', nargs=3, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempts), indent=2))


if __name__ == '__main__':
    main()
