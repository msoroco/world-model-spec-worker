"""CPU-only check of original CARLA readback and Native saved-source joins."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / '.runtime-work' / 'c111294-yield-source-proof' / 'yield'
TARGET = ROOT / '.runtime-work' / 'c111294-native-source-proof'


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = load('c111294_runner', HERE / 'native' / 'runner.py')
measure = load('c111294_measure', HERE / 'native' / 'measure_yield.py')
sys.path.insert(0, str(HERE / 'native'))
live = load('c111294_live', HERE / 'native' / 'live_capture.py')


class Obj:
    def __init__(self, **values):
        self.__dict__.update(values)


class Actor:
    id = 3
    type_id = 'vehicle.tesla.model3'

    def __init__(self, x, y):
        self.pose = Obj(location=Obj(x=x, y=y, z=1.0), rotation=Obj(yaw=90.0))
        self.velocity = Obj(x=0.0, y=0.0, z=0.0)
        self.bounding_box = Obj(get_world_vertices=lambda pose: [
            Obj(x=x + (j % 2), y=y + (j // 2 % 2), z=1.0) for j in range(8)])

    def get_transform(self):
        return self.pose

    def get_velocity(self):
        return self.velocity


class Control:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Carla:
    VehicleControl = Control


def reject(action, expected):
    try:
        action()
    except ValueError as exc:
        assert expected in str(exc), str(exc)
        return str(exc)
    raise AssertionError('Invalid original source passed')


def main():
    through = Actor(-1.75, -50.0)
    entrant = Actor(-12.0, 1.75)
    tw, ew = Obj(road_id=4, lane_id=1), Obj(road_id=3, lane_id=-1)
    row = runner.capture_row(0, 211, 0.05, through, entrant, tw, ew)
    assert row['through']['y_m'] == 50.0
    assert row['entrant']['y_m'] == -1.75
    assert row['through']['lane_id'] == 1 and row['entrant']['lane_id'] == -1
    assert len(row['through']['body_vertices_m']) == 8
    assert reject(lambda: runner.capture_row(0, 211, 0.05, through, entrant, None, ew),
                  'projection absent')
    stop = live.command(Carla, through, 0.0, (-1.75, -30), 90)
    go = live.command(Carla, through, 8.0, (-1.75, -30), 90)
    assert stop.brake == 1.0 and stop.throttle == 0.0
    assert go.throttle > 0.0
    nominal_hold_y = live.THROUGH_START_AUTHORED_Y_M - 8.0 * 142 / runner.RATE_HZ
    assert nominal_hold_y > 7.0
    TARGET.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE / 'road.xodr', TARGET / 'road.xodr')
    rows = [json.loads(line) for line in (SOURCE / 'native_samples.jsonl').read_text().splitlines()]
    for index, item in enumerate(rows):
        item['native_frame'] = 211 + index
        item['time_s'] = .05 + index / 20
        item['source_kind'] = 'native_observation'
    sample_path = TARGET / 'native_samples.jsonl'
    sample_path.write_text(''.join(json.dumps(item, sort_keys=True) + '\n' for item in rows))
    manifest = {'case_id': HERE.name + '__probe_1', 'source_kind': 'native_observation',
                'sha256': {name: hashlib.sha256((TARGET / name).read_bytes()).hexdigest()
                           for name in ('road.xodr', 'native_samples.jsonl')}}
    (TARGET / 'diagnostic-source-manifest.json').write_text(json.dumps(manifest) + '\n')
    observed = measure.measure(TARGET, manifest['case_id'])
    assert observed['source_kind'] == 'native_observation'
    assert observed['through_yield_response_observed']
    rows[240]['native_frame'] += 2
    sample_path.write_text(''.join(json.dumps(item, sort_keys=True) + '\n' for item in rows))
    manifest['sha256']['native_samples.jsonl'] = hashlib.sha256(sample_path.read_bytes()).hexdigest()
    (TARGET / 'diagnostic-source-manifest.json').write_text(json.dumps(manifest) + '\n')
    reject(lambda: measure.measure(TARGET, manifest['case_id']), 'Original frame join differs')
    print(json.dumps({'passed': True, 'positive_capture_rows': 1,
                      'native_saved_positive': 1, 'negative_checks': 2}, sort_keys=True))


if __name__ == '__main__':
    main()
