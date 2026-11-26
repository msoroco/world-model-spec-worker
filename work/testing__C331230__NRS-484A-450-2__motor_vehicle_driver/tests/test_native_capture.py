import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
for name in ('near_crosswalk', 'native_capture'):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
near = sys.modules['near_crosswalk']
capture = sys.modules['native_capture']


class Vehicle:
    id = 7
    type_id = 'vehicle.tesla.model3'
    is_alive = True
    bounding_box = SimpleNamespace(extent=SimpleNamespace(x=1.0),
        get_world_vertices=lambda transform: [SimpleNamespace(x=transform.location.x + dx,
            y=transform.location.y + dy, z=0.0)
            for dx, dy in ((-1., -1.), (-1., 1.), (1., -1.), (1., 1.))])

    def __init__(self, world):
        self.world = world

    def get_transform(self):
        i = self.world.index
        front = 1.0 if i < 200 else 9.0 if i < 300 else 15.0
        return SimpleNamespace(location=SimpleNamespace(x=front - 1.0, y=10.0, z=0.0),
                               get_forward_vector=lambda: SimpleNamespace(x=1.0, y=0.0))

    def get_velocity(self):
        speed = 0.0 if self.world.halt and self.world.index == 150 else 1.0
        return SimpleNamespace(length=lambda: speed)

    def destroy(self):
        self.is_alive = False


class World:
    def __init__(self, halt):
        self.halt = halt
        self.index = -1
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.vehicle = Vehicle(self)
        self.restored = False

    def get_settings(self):
        return copy.copy(self.settings)

    def apply_settings(self, settings):
        self.settings = copy.copy(settings)
        self.restored = not settings.synchronous_mode

    def tick(self):
        self.index += 1
        return self.index + 101

    def get_snapshot(self):
        return SimpleNamespace(frame=self.index + 101,
                               timestamp=SimpleNamespace(elapsed_seconds=self.index / 20))


class Operator:
    def __init__(self, site, world):
        self.site = site
        self.world = world
        self.sensors = []

    def map_bytes(self, world):
        return b'reviewed-map'

    def site_readback(self, world, site):
        return {key: site[key] for key in (
            'stop_sign_id', 'stop_sign_orientation_xy', 'stop_sign_governs',
            'intersection_rect_m', 'near_crosswalk_rect_m', 'marked',
            'opposing_sidewalk_left_xy', 'opposing_sidewalk_right_xy')}

    def spawn_vehicle(self, xy):
        return self.world.vehicle

    def set_stop_sign(self, governs):
        pass

    def set_crosswalk(self, rect, marked):
        pass

    def set_vehicle_route(self, vehicle, route, halt, entry):
        pass

    def control(self, vehicle, site, case, brake_distance_m):
        pass

    def observe(self, world, actor, frame, site):
        return {'source_frame_id': frame, 'actor_id': actor.id, 'ego_alive': True,
                'road_id': site['road_id'], 'lane_id': site['lane_id']}

    def cameras(self, world, actor, views):
        sensor = SimpleNamespace(stop=lambda: None, destroy=lambda: None)
        return {view: lambda frame: b'PNG' + str(frame).encode() for view in views}, [sensor]


def site_for(folder, case):
    packet = {'source_kind': 'reviewed_original_native_crosswalk_site',
              'assignment_id': capture.ASSIGNMENT,
              'case_ids': [capture.ASSIGNMENT + '__' + item.name for item in near.CASES],
              'cell_id': 'C331230', 'actor': 'motor_vehicle_driver',
              'qualifying_vehicle': True, 'driver_control': True,
              'driver_id': 'd1', 'vehicle_id': 'v1',
              'marked': case.marked, 'halt': case.halt,
              'stop_sign_governs': True, 'stop_sign_id': 'S1',
              'stop_sign_orientation_xy': [-1.0, 0.0],
              'map_sha256': hashlib.sha256(b'reviewed-map').hexdigest(),
              'road_id': 4, 'lane_id': 1,
              'intersection_rect_m': [10., 0., 30., 20.],
              'near_crosswalk_rect_m': [8., 0., 10., 20.],
              'opposing_sidewalk_left_xy': [8., 0.],
              'opposing_sidewalk_right_xy': [8., 20.],
              'vehicle_route_xy': [[0., 10.], [20., 10.]],
              'crosswalk_entry_frame': 200, 'source_records': {}}
    for name in near.SOURCES:
        data = (name + ':reviewed').encode()
        (folder / (name + '.txt')).write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        packet[name + '_source_sha256'] = digest
        packet['source_records'][name] = {'path': name + '.txt', 'sha256': digest}
    path = folder / 'site.json'
    path.write_text(json.dumps(packet) + '\n')
    return path, hashlib.sha256(path.read_bytes()).hexdigest(), packet


class NativeCaptureTests(unittest.TestCase):
    def test_900_original_frames_and_restoration_for_all_cases(self):
        for case in near.CASES:
            with self.subTest(case=case.name), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                path, digest, packet = site_for(folder, case)
                world = World(case.halt)
                measured = capture.capture(world, case_id=capture.ASSIGNMENT + '__' + case.name,
                    site_path=path, site_sha256=digest, output=folder / 'attempt',
                    operator=Operator(packet, world))
                self.assertEqual(measured['crosswalk_entry_frame'], 301)
                self.assertEqual(measured['stopped_before_entry'], case.halt)
                self.assertTrue(world.restored)
                self.assertFalse(world.vehicle.is_alive)
                self.assertEqual(len(json.loads((folder / 'attempt/history.json').read_text())), 900)

    def test_source_mutation_rejected_before_native_world_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            case = near.CASES[0]
            path, digest, packet = site_for(folder, case)
            (folder / 'stop_sign_orientation.txt').write_text('mutated')
            world = World(True)
            with self.assertRaisesRegex(ValueError, 'source bytes changed'):
                capture.capture(world, case_id=capture.ASSIGNMENT + '__' + case.name,
                    site_path=path, site_sha256=digest, output=folder / 'attempt',
                    operator=Operator(packet, world))
            self.assertEqual(world.index, -1)


if __name__ == '__main__':
    unittest.main()
