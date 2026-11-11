"""CPU check of authored following-gap setpoints; no physical feasibility claim.

This probes the exact controller used by the Native runner at fixed, supplied
actor states. It establishes that a gap grid changes commands in the intended
direction. Realized spacing, body dimensions and route feasibility require the
original Native state and remain outside this probe.
"""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from following_controller import FollowingController


GRID_M = (7.0, 8.5, 10.0)


class Actor:
    def __init__(self, x, speed):
        self.x, self.speed, self.control = x, speed, None

    def get_location(self):
        return SimpleNamespace(x=self.x, y=0.0, z=0.0)

    def get_velocity(self):
        return SimpleNamespace(x=self.speed, y=0.0, z=0.0)

    def apply_control(self, control):
        self.control = control


def probe(config):
    if config['requested_engineering_gap_m'] != 10.0:
        raise ValueError('Probe requires the reviewed base controller configuration')
    results = []
    for gap in GRID_M:
        ego, lead = Actor(0.0, 4.0), Actor(13.0, 3.5)
        controller = FollowingController(
            SimpleNamespace, target_speed_mps=config['ego_target_speed_mps'],
            target_center_spacing_m=gap + 4.0,
            lane_change_start_m=55.0, lane_change_end_m=70.0,
            lead_speed_mps=config['lead_target_speed_mps'])
        state = controller.step(ego, lead,
            route_origin_xyz=(0.0, 0.0, 0.0), route_forward_xy=(1.0, 0.0),
            target_lane_center_xy=(0.0, 3.5))
        results.append({'requested_engineering_gap_m': gap,
                        'target_center_spacing_m': controller.target_spacing,
                        'fixed_measured_center_spacing_m': state['measured_center_spacing_m'],
                        'requested_engineering_speed_mps': state['requested_engineering_speed_mps'],
                        'ego_brake': state['ego_brake'],
                        'ego_throttle': state['ego_throttle']})
    speeds = [row['requested_engineering_speed_mps'] for row in results]
    brakes = [row['ego_brake'] for row in results]
    if not (speeds[0] > speeds[1] > speeds[2] and
            brakes[0] < brakes[1] < brakes[2]):
        raise ValueError('Gap grid did not change controller command monotonically')
    return {'format': 'c101303-controller-grid-probe',
            'diagnostic_only': True, 'physical_feasibility_proven': False,
            'legal_threshold_asserted': False,
            'duration_s': config['duration_s'], 'rate_hz': config['rate_hz'],
            'fixed_actor_state': {'ego_speed_mps': 4.0, 'lead_speed_mps': 3.5,
                                  'center_spacing_m': 13.0, 'route_progress_m': 0.0},
            'points': results,
            'limitations': ['Single fixed synthetic actor state; no dynamics or collision model.',
                            'The runner adds 4 m to requested gap; actual body lengths must be read from Native source.',
                            'No original accepted trace or selected Native hill-crest motion is available in this export.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    result = probe(config)
    result['sources'] = {
        name: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        for name, path in [('config', args.config), ('controller', Path(__file__).with_name('following_controller.py')),
                           ('probe', Path(__file__))]}
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
