import json
import hashlib
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from carla_runner import run_capture
from test_native_capture import site


def obj(**values): return types.SimpleNamespace(**values)


class Sensor:
    def __init__(self): self.callback = None; self.stopped = False
    def listen(self, callback): self.callback = callback
    def stop(self): self.stopped = True


class Actor:
    def __init__(self, identifier, y):
        self.id, self.y = identifier, y
        self.controls = []
        self.bounding_box = obj(get_world_vertices=lambda transform: [
            obj(x=float(n % 2), y=self.y, z=float(n // 4)) for n in range(8)])
    def get_transform(self):
        return obj(location=obj(x=0.0, y=self.y),
                   get_forward_vector=lambda: obj(x=0.0, y=-1.0))
    def get_velocity(self): return obj(length=lambda: 1.0)
    def get_location(self): return obj(x=0.0, y=self.y)
    def apply_control(self, control): self.controls.append(control)


class World:
    def __init__(self, ego, other, sensors, bad_other=False):
        self.ego, self.other, self.sensors = ego, other, sensors
        self.bad_other = bad_other
        self.frame = 100
        self.positions = [5.0, 0.0, 0.0, -3.0]
    def get_settings(self): return obj(synchronous_mode=True, fixed_delta_seconds=.05)
    def get_map(self): return self
    def to_opendrive(self): return 'original-test-opendrive'
    def get_waypoint(self, location, project_to_road=False):
        if location.y == self.other.y:
            return obj(lane_id='west' if self.bad_other else 'east')
        return obj(lane_id='approach' if location.y == 5 else
                   'center' if location.y == 0 else 'east')
    def tick(self):
        self.frame += 1
        self.ego.y = self.positions[self.frame - 101]
        for sensor in self.sensors.values():
            sensor.callback(obj(frame=self.frame, width=2, height=2,
                                raw_data=bytes([1, 2, 3, 255] * 4)))
        return self.frame
    def get_snapshot(self):
        return obj(frame=self.frame, timestamp=obj(elapsed_seconds=self.frame * .05))


class CarlaRunnerTests(unittest.TestCase):
    def setUp(self):
        Path('.runtime-work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir='.runtime-work')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet = site(self.root)
        map_source = self.root / self.packet['native_map_source']['path']
        map_source.write_text(json.dumps({'opendrive_sha256':
            hashlib.sha256(b'original-test-opendrive').hexdigest()}) + '\n')
        self.packet['native_map_source']['sha256'] = hashlib.sha256(map_source.read_bytes()).hexdigest()
        self.ego, self.other = Actor(11, 5.0), Actor(12, -3.0)
        self.sensors = {view: Sensor() for view in
            ('overview', 'approach', 'reference_corner', 'driver_reference')}
        self.world = World(self.ego, self.other, self.sensors)
        self.route = [[0, 5], [0, 0], [5, 0], [5, -3]]
    def run_case(self, **changes):
        args = dict(attempt_root=self.root, case_id='exact__below_50ft',
                    site=self.packet, world=self.world, ego=self.ego,
                    receiving_vehicle=self.other, cameras=self.sensors,
                    route_xy_m=self.route, control_factory=lambda **kw: obj(**kw),
                    count=4, dimensions={view: (2, 2) for view in self.sensors})
        args.update(changes)
        return run_capture(**args)
    def test_live_frame_reader_seals_observed_turn_merge_and_traffic(self):
        receipt = self.run_case()
        self.assertTrue(receipt['delivered_measurement']['merge_observed'])
        trace = json.loads((self.root / 'native/trace.json').read_text())
        self.assertEqual([row['left_turn_onto_highway_complete'] for row in trace['samples']],
                         [False, True, False, False])
        self.assertEqual([row['merged_into_through_lane'] for row in trace['samples']],
                         [False, False, False, True])
        self.assertEqual({row['receiving_vehicle_actor_id'] for row in trace['samples']}, {12})
        self.assertTrue(all(sensor.stopped for sensor in self.sensors.values()))
        self.assertEqual(len(self.ego.controls), 4)
    def test_changed_receiving_lane_rejects_and_releases_sensors(self):
        self.world.bad_other = True
        with self.assertRaisesRegex(ValueError, 'receiving traffic left'):
            self.run_case()
        self.assertTrue(all(sensor.stopped for sensor in self.sensors.values()))
        self.assertFalse((self.root / 'native/trace.json').exists())

    def test_live_map_mismatch_rejected_before_motion(self):
        self.world.to_opendrive = lambda: 'different-map'
        with self.assertRaisesRegex(ValueError, 'live OpenDRIVE differs'):
            self.run_case()
        self.assertEqual(self.ego.controls, [])


if __name__ == '__main__': unittest.main()
