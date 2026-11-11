"""Probe where the authored gap grid separates controller commands.

These are independent synthetic actor states, not a Native motion trace or a
claim that any requested body gap is physically feasible.
"""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from following_controller import FollowingController
from sweep_probe import Actor, GRID_M


SPACINGS_M = (8.0, 10.0, 12.0, 13.0, 14.0, 16.0, 20.0)
LEAD_SPEEDS_MPS = (2.5, 3.5, 5.0)
PHASES = (('before_lane_change', 0.0), ('after_lane_change', 75.0))


def probe(config):
    if (config['requested_engineering_gap_m'] != 10.0 or
            config['minimum_corridor_length_m'] != 100.0 or
            config['ego_target_speed_mps'] != 4.0):
        raise ValueError('Envelope requires the reviewed base engineering configuration')
    rows = []
    for phase, progress in PHASES:
        for lead_speed in LEAD_SPEEDS_MPS:
            for spacing in SPACINGS_M:
                commands = []
                for gap in GRID_M:
                    ego, lead = Actor(progress, 4.0), Actor(progress + spacing, lead_speed)
                    controller = FollowingController(
                        SimpleNamespace, target_speed_mps=config['ego_target_speed_mps'],
                        target_center_spacing_m=gap + 4.0,
                        lane_change_start_m=55.0, lane_change_end_m=70.0,
                        lead_speed_mps=config['lead_target_speed_mps'])
                    state = controller.step(ego, lead,
                        route_origin_xyz=(0.0, 0.0, 0.0), route_forward_xy=(1.0, 0.0),
                        target_lane_center_xy=(0.0, 3.5))
                    commands.append(state['requested_engineering_speed_mps'])
                if not commands[0] >= commands[1] >= commands[2]:
                    raise ValueError('Controller reversed the gap-grid command order')
                rows.append({'phase': phase, 'route_progress_m': progress,
                             'center_spacing_m': spacing, 'lead_speed_mps': lead_speed,
                             'requested_speed_mps_by_gap': commands,
                             'all_three_distinct': commands[0] > commands[1] > commands[2]})
    if not any(row['all_three_distinct'] for row in rows):
        raise ValueError('No synthetic actor state separates the gap grid')
    return {'format': 'c101303-controller-envelope-probe', 'diagnostic_only': True,
            'physical_feasibility_proven': False, 'legal_threshold_asserted': False,
            'requested_gap_grid_m': list(GRID_M),
            'fixed_ego_speed_mps': 4.0, 'states': rows,
            'distinct_state_count': sum(row['all_three_distinct'] for row in rows),
            'state_count': len(rows),
            'interpretation': 'Controller command separability across independently supplied synthetic states; no dynamics, complete-body geometry, or realized spacing.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = probe(json.loads(args.config.read_text()))
    result['sources'] = {name: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                         for name, path in (('config', args.config),
                            ('controller', Path(__file__).with_name('following_controller.py')),
                            ('grid', Path(__file__).with_name('sweep_probe.py')),
                            ('envelope', Path(__file__)))}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'format': result['format'], 'state_count': result['state_count'],
                      'distinct_state_count': result['distinct_state_count'],
                      'physical_feasibility_proven': False,
                      'output_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
