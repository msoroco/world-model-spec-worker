"""Exercise exact Native request validation and both controller schedules without CARLA."""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


class FakeCarla:
    class VehicleControl:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


def configuration(case, candidate):
    cameras = []
    for name, width, height, xyz, pyr in (
        ('overview', 1920, 1080, [0, 0, 28], [-75, 0, 0]),
        ('approach', 1280, 720, [0, 0, 2.4], [-5, 0, 0]),
        ('reference_corner', 1280, 720, [2, 1, 1.8], [-12, -45, 0]),
        ('driver_reference', 1280, 720, [0, 0, 1.8], [-10, 0, 0])):
        cameras.append({'name': name, 'width': width, 'height': height,
                        'fps': 20, 'fov_deg': 90,
                        'location_xyz_m': xyz, 'rotation_pyr_deg': pyr})
    return {'case_id': HERE.parent.name + '__' + case,
            'selected_case_id': HERE.parent.name + '__' + case,
            'cell_id': 'C111603', 'law_id': 'NRS-484B-307-7a',
            'actor': 'motor_vehicle_driver', 'candidate_id': candidate,
            'duration_s': 30, 'rate_hz': 20,
            'ego_release_frame': 320 if case == 'controlled_1' else 200,
            'ego_throttle': 0.22 if candidate == 'primary' else 0.28,
            'other_throttle': 0.18,
            'pedestrian_lawful_status': None,
            'other_traffic_lawful_status': None,
            'cautiousness_legal_judgment': None,
            'cameras': cameras, 'required_atoms': []}


def prove():
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location('native_runner', HERE / 'native_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    evidence = []
    for case in ('controlled_1', 'controlled_2'):
        for candidate in ('primary', 'fallback1'):
            config = configuration(case, candidate)
            checked = module.check(config)
            release = config['ego_release_frame']
            before, other_before = module.control_for(config, release - 1, FakeCarla)
            after, other_after = module.control_for(config, release, FakeCarla)
            last, _ = module.control_for(config, 599, FakeCarla)
            if (before.brake != 1 or before.throttle != 0 or
                    after.brake != 0 or after.throttle != config['ego_throttle'] or
                    after.steer != 0.30 or last.steer != 0 or
                    other_before.throttle != other_after.throttle or
                    checked['legal_verdict_claimed']):
                raise AssertionError('Controlled Native request differs')
            evidence.append({'case': case, 'candidate': candidate,
                             'release_frame': release, 'check': checked})
            for key, changed in (
                ('duration_s', 29), ('ego_release_frame', 205),
                ('other_traffic_lawful_status', 'lawful')):
                altered = dict(config, **{key: changed})
                try:
                    module.check(altered)
                except ValueError:
                    pass
                else:
                    raise AssertionError('Invalid ' + key + ' was accepted')
    return {'passed': True, 'native_executed': False,
            'source_plan': '30 s / 600 frames / 20 Hz / four cameras',
            'cases': evidence}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
