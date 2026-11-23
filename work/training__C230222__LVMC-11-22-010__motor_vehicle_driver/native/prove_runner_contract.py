"""CPU checks for the proposed C230222 original-capture configuration."""
import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('c230222_runner', HERE / 'native_runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
config = json.loads((HERE / 'config.json').read_text())


def rejected(changed, message):
    try:
        runner.check(changed)
    except ValueError as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError('Invalid capture configuration accepted')


def main():
    check = runner.check(config)
    assert check['frames'] == 600 and check['rate_hz'] == 20
    assert len(check['camera_views']) == 4 and check['carla_contacted'] is False
    assert check['attention_observed'] is False
    assert [runner.phase_at(config, frame)['name'] for frame in
            (0, 199, 200, 479, 480, 599)] == [
                'approach', 'approach', 'travel', 'travel', 'departure', 'departure']
    assert len([runner.phase_at(config, frame) for frame in range(600)]) == 600
    changed = copy.deepcopy(config)
    changed['case_id'] += '-wrong'
    rejected(changed, 'identity')
    changed = copy.deepcopy(config)
    changed['duration_s'] = 10
    rejected(changed, 'duration')
    changed = copy.deepcopy(config)
    changed['cameras'].pop()
    rejected(changed, 'Four named')
    changed = copy.deepcopy(config)
    changed['cameras'][0]['fov_deg'] = 180
    rejected(changed, 'pose or optics')
    changed = copy.deepcopy(config)
    changed['control_phases'][1]['first_frame'] = 201
    rejected(changed, 'gap')
    changed = copy.deepcopy(config)
    changed['control_phases'][-1]['last_frame'] = 598
    rejected(changed, 'frame 599')
    changed = copy.deepcopy(config)
    changed['driver_attention_to_operation'] = True
    rejected(changed, 'identity')
    changed = copy.deepcopy(config)
    changed['cameras'][0]['location_xyz_m'][0] = float('nan')
    rejected(changed, 'pose or optics')
    print(json.dumps({'passed': True, 'frames': 600, 'rate_hz': 20,
                      'camera_views': 4, 'phase_boundaries_checked': 6,
                      'negative_configurations_rejected': 8,
                      'carla_contacted': False, 'native_execution_proven': False,
                      'driver_attention_observed': False}))


if __name__ == '__main__':
    main()
