import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pathing import repository_root
from test_statutory_variants import survey
from variant_capture import acquire, sample


def xyz(x, y, z=0):
    return types.SimpleNamespace(x=x, y=y, z=z)


class Ego:
    id = 10
    type_id = 'vehicle.example'

    def __init__(self):
        self.bounding_box = types.SimpleNamespace(
            get_world_vertices=lambda _: [xyz(x, y) for x, y in
                                           ((0, 0), (1, 0), (1, 1), (0, 1))] * 2)

    def get_transform(self):
        return types.SimpleNamespace(location=xyz(-5, 0),
                                     rotation=types.SimpleNamespace(yaw=0))

    def get_velocity(self):
        return xyz(3, 4)

    def apply_control(self, value):
        self.last_control = value

    def destroy(self):
        pass


class Sensor:
    def listen(self, callback):
        self.callback = callback

    def stop(self):
        pass

    def destroy(self):
        pass


class World:
    def __init__(self):
        self.frame = 0
        self.sensors = []
        self.ego = Ego()
        self.control = types.SimpleNamespace(id=12,
            type_id='static.prop.trafficwarning',
            get_transform=lambda: types.SimpleNamespace(location=xyz(2, 0)))
        self.settings = types.SimpleNamespace(synchronous_mode=False,
                                              fixed_delta_seconds=None)

    def get_map(self):
        return types.SimpleNamespace(name='surveyed-map',
            get_waypoint=lambda *args, **kwargs: types.SimpleNamespace(
                road_id=8, lane_id=1, lane_type='Driving'),
            to_opendrive=lambda: '<OpenDRIVE/>')

    def get_actors(self):
        return types.SimpleNamespace(find=lambda ident: self.control if ident == 12 else None)

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def get_blueprint_library(self):
        blueprint = types.SimpleNamespace(set_attribute=lambda *args: None)
        return types.SimpleNamespace(find=lambda name: blueprint)

    def try_spawn_actor(self, blueprint, transform):
        return self.ego

    def spawn_actor(self, blueprint, transform, attach_to):
        sensor = Sensor()
        self.sensors.append(sensor)
        return sensor

    def tick(self):
        self.frame += 1
        for sensor in self.sensors:
            sensor.callback(types.SimpleNamespace(frame=self.frame))
        return self.frame

    def get_snapshot(self):
        return types.SimpleNamespace(timestamp=types.SimpleNamespace(
            elapsed_seconds=self.frame * .05))


CARLA = types.SimpleNamespace(
    Location=lambda **kwargs: types.SimpleNamespace(**kwargs),
    Rotation=lambda **kwargs: types.SimpleNamespace(**kwargs),
    Transform=lambda location, rotation: types.SimpleNamespace(
        location=location, rotation=rotation),
    VehicleControl=lambda **kwargs: types.SimpleNamespace(**kwargs),
    LaneType=types.SimpleNamespace(Any='Any', Driving='Driving', Shoulder='Shoulder'))


class Sink:
    def __init__(self, *args):
        self.count = 0

    def write(self, image):
        self.count += 1

    def close(self):
        pass


class VariantCaptureTest(unittest.TestCase):
    def test_source_sample_uses_control_actor_and_original_velocity(self):
        world = World()
        row = sample(world, CARLA, world.ego, world.control, {'steer': .1})
        self.assertEqual(row['ego_velocity_xyz_mps'], [3, 4, 0])
        self.assertEqual(row['ego_speed_mps'], 5)
        self.assertEqual(row['control_type_id'], 'static.prop.trafficwarning')
        self.assertFalse(row['control_content_verified'])

    def test_employee_sample_keeps_separate_warning_actor(self):
        world = World()
        worker = types.SimpleNamespace(id=12, type_id='walker.pedestrian.0001',
            get_transform=lambda: types.SimpleNamespace(location=xyz(2, 0)))
        warning = types.SimpleNamespace(id=13, type_id='static.prop.trafficwarning',
            is_alive=True,
            get_transform=lambda: types.SimpleNamespace(location=xyz(3, 0)))
        row = sample(world, CARLA, world.ego, worker, {'steer': .1}, warning)
        self.assertEqual(row['control_actor_id'], 12)
        self.assertEqual(row['governing_warning_control']['actor_id'], 13)
        self.assertFalse(row['employee_exception_verified'])

    def test_600_frame_selected_variant_capture_keeps_sources(self):
        repo = repository_root(__file__)
        (repo / '.runtime-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=repo / '.runtime-work') as name:
            attempt = Path(name)
            row = survey('barrier')
            case_id = 'training__C183370__LVMC-11-22-100__motor_vehicle_driver__barrier_crossing'
            construction = b'{"case_id":"barrier_crossing"}\n'
            (attempt / 'construction.json').write_bytes(construction)
            (attempt / 'config.json').write_text(json.dumps({
                'case_suffix': 'crossing', 'selected_case_id': case_id,
                'case_id': case_id, 'frames': 600,
                'controller_knobs': {'speed_mps': 4, 'reach_m': 1.5,
                                     'steer_divisor_deg': 40}}))
            (attempt / 'candidate-selection.json').write_text(json.dumps({
                'case_id': case_id,
                'construction_sha256': hashlib.sha256(construction).hexdigest()}))
            world = World()
            client = types.SimpleNamespace(get_world=lambda: world)
            receipt = acquire(row, 'crossing', attempt, client, CARLA,
                              sink_factory=Sink)
            self.assertEqual(receipt['source_frames'], 600)
            self.assertEqual(receipt['control_kind'], 'barrier')
            self.assertEqual(len((attempt / 'native-actors.jsonl').read_text().splitlines()), 600)
            trace = json.loads((attempt / 'trace.jsonl').read_text().splitlines()[0])
            self.assertEqual(trace['speed_provenance'], 'original_carla_velocity')
            self.assertEqual(len(world.sensors), 4)
            self.assertFalse(world.settings.synchronous_mode)
            with self.assertRaisesRegex(ValueError, 'Preserve prior variant capture'):
                acquire(row, 'crossing', attempt, client, CARLA,
                        sink_factory=Sink)


if __name__ == '__main__':
    unittest.main()
