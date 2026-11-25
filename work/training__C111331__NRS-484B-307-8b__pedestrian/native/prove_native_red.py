"""CPU source/geometry/controller proof for the unselected Native construction."""

import copy
import json
from pathlib import Path

from native_red import (BOUNDARY_Y, CAMERAS, CONDITIONS, FRAMES, check_map,
                        check_plan, configure_heads, measure_entry, plan,
                        requested_speed, resolve_heads, sample_heads, sha)

HERE = Path(__file__).resolve().parent


class FakeHead:
    type_id = 'traffic.traffic_light'

    def __init__(self, od_id, actor_id):
        self.od_id, self.id = od_id, actor_id
        self.state = 'TrafficLightState.Red'
        self.frozen = False

    def get_opendrive_id(self):
        return self.od_id

    def get_state(self):
        return self.state

    def set_state(self, value):
        self.state = value

    def freeze(self, value):
        self.frozen = value


class FakeCarla:
    class TrafficLightState:
        Red = 'TrafficLightState.Red'
        Green = 'TrafficLightState.Green'


def reject(function, message):
    try:
        function()
    except ValueError as exc:
        if message not in str(exc):
            raise AssertionError(f'Wrong rejection: {exc}') from exc
        return
    raise AssertionError('Missing expected rejection: ' + message)


def rows_for(config):
    rows = []
    y = config['walker_start_xy_m'][1]
    for frame in range(FRAMES):
        y -= requested_speed(config['condition'], frame) / 20
        feet = [[x, y + dy] for x, dy in ((7.8, -.2), (7.8, .2), (8.2, -.2), (8.2, .2))]
        rows.append({'video_frame': frame, 'footprint_xy_m': feet,
                     'traffic': {'state': 'red'},
                     'other': {'state': config['requested_other_device']}})
    return rows


def main():
    geometry = check_map()
    positives, negatives, cases = 0, 0, []
    for condition in CONDITIONS:
        config = plan(condition)
        check_plan(config)
        rows = rows_for(config)
        measurement = measure_entry(rows, config)
        assert bool(measurement['first_roadway_footprint_frame'] is not None) == config['requested_entry']
        assert rows[0]['footprint_xy_m'][0][1] > BOUNDARY_Y
        assert measurement['legal_verdict'] is None
        positives += 1
        cases.append({'case_id': config['case_id'], 'first_entry_frame': measurement['first_roadway_footprint_frame'],
                      'other_indication': config['requested_other_device']})
        damaged = copy.deepcopy(rows)
        damaged[220]['traffic']['state'] = 'green'
        reject(lambda: measure_entry(damaged, config), 'changed red-entry source')
        negatives += 1
        damaged = copy.deepcopy(rows)
        del damaged[0]['footprint_xy_m']
        reject(lambda: measure_entry(damaged, config), 'footprint incomplete')
        negatives += 1
        fallback = plan(condition, 'fallback1')
        check_plan(fallback)
        assert fallback['walker_start_xy_m'][1] > config['walker_start_xy_m'][1]
        positives += 1
    heads = resolve_heads([FakeHead('301', 100), FakeHead('302', 101)])
    assert configure_heads(heads, plan('exception_permits'), FakeCarla)['other']['state'] == 'walk'
    assert all(head.frozen for head in heads.values())
    positives += 1
    reject(lambda: resolve_heads([FakeHead('301', 100)]), 'Both distinct')
    negatives += 1
    reject(lambda: resolve_heads([FakeHead('301', 100), FakeHead('301', 102), FakeHead('302', 101)]), 'Ambiguous')
    negatives += 1
    heads['301'].state = 'TrafficLightState.Green'
    assert sample_heads(heads)['traffic']['state'] == 'green'
    class StuckHead(FakeHead):
        def set_state(self, value):
            self.state = 'TrafficLightState.Green'
    stuck = resolve_heads([StuckHead('301', 100), FakeHead('302', 101)])
    reject(lambda: configure_heads(stuck, plan('condition_a'), FakeCarla),
           'Native head readback differs')
    negatives += 1
    assert [name for name, _, _, _ in CAMERAS] == [
        'overview', 'approach', 'reference_corner', 'driver_reference']
    receipt = {'format': 'c111331-native-red-cpu-proof-v1',
               'positive_checks': positives, 'negative_checks': negatives,
               'cases': cases, 'geometry': geometry,
               'runner_sha256': sha(HERE / 'runner.py'),
               'controller_sha256': sha(HERE / 'native_red.py'),
               'native_executed': False,
               'device_governance_verified': False,
               'physical_pixels_verified': False,
               'legal_verdict_claimed': False}
    output = HERE.parent / 'native-red-cpu-proof.json'
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'receipt_sha256': sha(output), 'positive_checks': positives,
                      'negative_checks': negatives}, sort_keys=True))


if __name__ == '__main__':
    main()
