"""Exercise all exact Native runner preflights without importing CARLA."""

import json
from pathlib import Path

from runner import check


def reject(fn, phrase):
    try:
        fn()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


plan = json.loads((Path(__file__).resolve().parents[1] / 'case-plan.json').read_text())
dimensions = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
names = ('overview', 'approach', 'reference_corner', 'driver_reference')
cameras = [{'name': name, 'width': size[0], 'height': size[1], 'fps': 20,
            'fov_deg': 85, 'yaw_deg': 0, 'pitch_deg': -15,
            'mount_xyz_relative_to_crossing_m': [-10, 10, 12]}
           for name, size in zip(names, dimensions)]
for case in plan['cases']:
    for candidate, gain in (('primary', 1.0), ('fallback1', 1.25)):
        cfg = {'case_id': case['case_id'], 'law_id': plan['law_id'],
               'cell_id': plan['cell_id'], 'actor': plan['actor'],
               'rate_hz': 20, 'duration_frames': 600, 'duration_s': 30,
               'candidate_id': candidate, 'speed_mode': case['construction_design']['speed_mode'],
               'feedback_gain': gain, 'ego_blueprint_filter': 'vehicle.*',
               'required_atoms': [], 'cameras': cameras}
        assert check(cfg)['simulation_started'] is False
        reject(lambda: check(dict(cfg, duration_frames=599)), '600 original')
        reject(lambda: check(dict(cfg, actor='rail_vehicle')), 'identity')
        reject(lambda: check(dict(cfg, cameras=cameras[:3])), 'four original')
        reject(lambda: check(dict(cfg, candidate_id='unreviewed')), 'candidate')
print('PASS: 10 exact cases x 2 declared Native candidates and negative preflights')
