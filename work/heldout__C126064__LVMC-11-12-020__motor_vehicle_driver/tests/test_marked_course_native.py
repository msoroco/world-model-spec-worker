import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from marked_course_native import CAMERAS, FourCameraCapture, control_step, drive_turn, execute_marked_turn, place_markers, turn_targets


class Location:
    def __init__(self, x, y):
        self.x, self.y = x, y


class Transform:
    def __init__(self, x, y):
        self.location = Location(x, y)


class Actor:
    def __init__(self, transform, offset=0):
        self.transform, self.offset, self.destroyed = transform, offset, False

    def get_transform(self):
        return Transform(self.transform.location.x + self.offset, self.transform.location.y)

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, junction=True, offset=0):
        self.junction, self.offset, self.actors = junction, offset, []

    def get_blueprint_library(self):
        return self

    def get_map(self):
        return self

    def find(self, name):
        assert name == 'static.prop.road_marker'
        return name

    def get_waypoint(self, location):
        return type('Waypoint', (), {'is_junction': self.junction})()

    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(transform, self.offset)
        self.actors.append(actor)
        return actor


class NativeMarkerTests(unittest.TestCase):
    def source(self, root):
        p = root / 'authorized-course.json'
        p.write_text(json.dumps({'authority_document': 'reviewed city plan',
                                 'intersection_id': 'junction-7',
                                 'median_opening_with_intersecting_road': True,
                                 'markers': [{'x': 1, 'y': 2, 'z': 0, 'yaw': 90,
                                              'blueprint_id': 'static.prop.road_marker'}]}))
        return p, hashlib.sha256(p.read_bytes()).hexdigest()

    def test_actual_spawn_and_readback(self):
        with TemporaryDirectory() as td:
            p, digest = self.source(Path(td))
            world = World()
            result = place_markers(world, p, digest, lambda x, y, z, yaw: Transform(x, y))
            self.assertEqual(result['physical_marker_xy_m'], [[1.0, 2.0]])
            self.assertEqual(len(world.actors), 1)
            self.assertFalse(world.actors[0].destroyed)

    def test_source_junction_and_readback_rejection(self):
        with TemporaryDirectory() as td:
            p, digest = self.source(Path(td))
            with self.assertRaisesRegex(ValueError, 'hash changed'):
                place_markers(World(), p, '0' * 64, lambda x, y, z, yaw: Transform(x, y))
            with self.assertRaisesRegex(ValueError, 'junction'):
                place_markers(World(junction=False), p, digest, lambda x, y, z, yaw: Transform(x, y))
            world = World(offset=1)
            with self.assertRaisesRegex(ValueError, 'readback'):
                place_markers(world, p, digest, lambda x, y, z, yaw: Transform(x, y))
            self.assertTrue(world.actors[0].destroyed)

    def test_source_bound_compared_turn_targets(self):
        with TemporaryDirectory() as td:
            p, _ = self.source(Path(td))
            record = json.loads(p.read_text())
            record.update({
                'intersection_polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]],
                'indicated_course_xy_m': [[-2, 5], [3, 5], [7, 7], [12, 7]],
                'divergent_course_xy_m': [[-2, 5], [3, 3], [7, 3], [12, 7]],
            })
            p.write_text(json.dumps(record))
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            world = World()
            result = turn_targets(world, p, digest, 'divergent_course',
                                  lambda x, y, z, yaw: Transform(x, y))
            self.assertEqual(result['targets_xy_m'][1], [3, 3])
            self.assertFalse(result['actual_turn_observed'])
            with self.assertRaisesRegex(ValueError, 'source hash changed'):
                turn_targets(world, p, '0'*64, 'indicated_course',
                             lambda x, y, z, yaw: Transform(x, y))
            record['divergent_course_xy_m'] = record['indicated_course_xy_m']
            p.write_text(json.dumps(record))
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'no different target'):
                turn_targets(world, p, digest, 'divergent_course',
                             lambda x, y, z, yaw: Transform(x, y))
            with self.assertRaisesRegex(ValueError, 'junction'):
                turn_targets(World(junction=False), p, digest, 'indicated_course',
                             lambda x, y, z, yaw: Transform(x, y))

    def test_controller_steers_to_target_and_rejects_invalid_state(self):
        straight = control_step((0, 0), (1, 0), (0, 0), (5, 0))
        turn = control_step((0, 0), (1, 0), (0, 0), (5, 5))
        self.assertEqual(straight['steer'], 0)
        self.assertGreater(turn['steer'], 0)
        self.assertLessEqual(turn['throttle'], .4)
        with self.assertRaisesRegex(ValueError, 'engineering speed'):
            control_step((0, 0), (1, 0), (0, 0), (5, 0), target_speed_mps=20)

    def test_four_named_original_camera_lifecycle_and_join(self):
        class Blueprint:
            def __init__(self): self.attributes = {}
            def set_attribute(self, key, value): self.attributes[key] = value

        class Sensor:
            def __init__(self): self.stopped = self.destroyed = False
            def listen(self, callback): self.callback = callback
            def stop(self): self.stopped = True
            def destroy(self): self.destroyed = True

        class CameraWorld:
            def __init__(self): self.blueprints, self.sensors = [], []
            def get_blueprint_library(self): return self
            def find(self, name):
                self.blueprints.append(Blueprint())
                return self.blueprints[-1]
            def spawn_actor(self, blueprint, transform, attach_to):
                sensor = Sensor(); self.sensors.append(sensor); return sensor

        carla = type('Carla', (), {'Location': lambda *v: v,
                                  'Rotation': lambda *v: v,
                                  'Transform': lambda loc, rot: (loc, rot)})
        world = CameraWorld(); originals = []
        capture = FourCameraCapture(world, carla, object(),
                                    lambda name, image: originals.append((name, image.frame)))
        self.assertEqual(len(world.sensors), 4)
        self.assertTrue(all(bp.attributes['sensor_tick'] == '0.05' for bp in world.blueprints))
        for (name, (_, _, (width, height), _)), sensor in zip(CAMERAS.items(), world.sensors):
            sensor.callback(type('Image', (), {'frame': 7, 'width': width, 'height': height})())
        capture.wait_for_frame(7, timeout_s=.1)
        self.assertEqual(capture.verify([7]), {name: 1 for name in CAMERAS})
        self.assertEqual(set(name for name, _ in originals), set(CAMERAS))
        capture.close()
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))

    def test_ego_turn_records_original_body_and_camera_frames(self):
        class Ego:
            id = 7
            def __init__(self):
                self.x = 0.
                self.controls = []
                self.bounding_box = self
            def get_transform(self):
                return type('Pose', (), {'location': Location(self.x, 0),
                       'get_forward_vector': lambda _: Location(1, 0)})()
            def get_velocity(self): return Location(0, 0)
            def apply_control(self, control): self.controls.append(control)
            def get_world_vertices(self, transform):
                x = transform.location.x
                return [type('Vertex', (), {'x': x+dx, 'y': dy})()
                        for _ in (0, 1) for dx, dy in ((-.2, -.1), (.2, -.1),
                                                         (.2, .1), (-.2, .1))]
        class TurnWorld:
            def __init__(self, ego): self.ego, self.frame = ego, 0
            def get_settings(self):
                return type('Settings', (), {'synchronous_mode': True,
                                             'fixed_delta_seconds': .05})()
            def tick(self):
                self.frame += 1; self.ego.x += .5; return self.frame
            def get_snapshot(self):
                return type('Snapshot', (), {'frame': self.frame,
                       'timestamp': type('Stamp', (), {'elapsed_seconds': self.frame*.05})()})()
        class Cameras:
            def wait_for_frame(self, frame): pass
            def verify(self, frames): return {'overview': len(frames)}
        carla = type('Carla', (), {'VehicleControl': lambda **kw: kw})
        ego = Ego(); samples = []
        result = drive_turn(TurnWorld(ego), carla, ego,
                            {'targets_xy_m': [[0, 0], [1, 0], [2, 0]],
                             'actual_turn_observed': False}, Cameras(), samples.append)
        self.assertEqual(result['targets_reached'], 2)
        self.assertEqual(result['capture_frames'], 160)
        self.assertEqual(len(result['frames']), 160)
        self.assertEqual([sample['time_s'] for sample in samples],
                         [frame * .05 for frame in result['frames']])
        self.assertEqual([sample['frame'] for sample in samples], result['frames'])
        self.assertTrue(all(len(sample['corners_xy_m']) == 4 for sample in samples))
        self.assertEqual(ego.controls[-1]['brake'], 1.)
        short_ego = Ego()
        with self.assertRaisesRegex(ValueError, 'exceeded fixed capture duration'):
            drive_turn(TurnWorld(short_ego), carla, short_ego,
                       {'targets_xy_m': [[0, 0], [1, 0], [2, 0]],
                        'actual_turn_observed': False}, Cameras(), lambda _: None,
                       capture_frames=1)

    def test_marker_target_camera_and_original_source_orchestration(self):
        with TemporaryDirectory() as td:
            p, _ = self.source(Path(td))
            record = json.loads(p.read_text())
            record.update({'intersection_polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]],
                           'indicated_course_xy_m': [[-2, 5], [3, 5], [7, 7], [12, 7]],
                           'divergent_course_xy_m': [[-2, 5], [3, 3], [7, 3], [12, 7]]})
            p.write_text(json.dumps(record))
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            world = World()
            events = []
            class Recorder:
                def record_scene(self, case_id, source, digest, markers, ego_id):
                    events.append(('scene', case_id, ego_id))
                def on_frame(self, name, image): events.append(('image', name))
                def record_sample(self, sample): events.append(('body', sample['frame']))
                def seal(self): events.append(('seal',)); return {'frames': 1}
                def close(self): events.append(('recorder_close',))
            class Cameras:
                def __init__(self, world, carla, ego, callback):
                    events.append(('camera_open',))
                    self.callback = callback
                def close(self): events.append(('camera_close',))
            def fake_drive(world, carla, ego, plan, cameras, record_sample):
                self.assertEqual(plan['variant'], 'divergent_course')
                cameras.callback('overview', object())
                record_sample({'frame': 1})
                return {'frames': [1]}
            ego = type('Ego', (), {'id': 7})()
            result = execute_marked_turn(world, object(), ego, 'marked-turn-case', p, digest,
                                         'divergent_course',
                                         lambda x, y, z, yaw: Transform(x, y),
                                         Recorder(), camera_factory=Cameras, drive=fake_drive)
            self.assertEqual(result['physical_marker_xy_m'], [[1.0, 2.0]])
            self.assertFalse(result['authority_verified'])
            self.assertEqual(events[-2:], [('camera_close',), ('recorder_close',)])
            self.assertTrue(world.actors[0].destroyed)

    def test_orchestration_releases_owned_sources_after_turn_failure(self):
        with TemporaryDirectory() as td:
            p, _ = self.source(Path(td))
            record = json.loads(p.read_text())
            record.update({'intersection_polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]],
                           'indicated_course_xy_m': [[-2, 5], [3, 5], [7, 7], [12, 7]],
                           'divergent_course_xy_m': [[-2, 5], [3, 3], [7, 3], [12, 7]]})
            p.write_text(json.dumps(record))
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            world = World()
            released = []
            class Recorder:
                def record_scene(self, case_id, source, digest, markers, ego_id): pass
                def on_frame(self, name, image): pass
                def record_sample(self, sample): pass
                def close(self): released.append('recorder')
            class Cameras:
                def __init__(self, world, carla, ego, callback): pass
                def close(self): released.append('cameras')
            def failing_drive(*args): raise ValueError('Native target failed')
            ego = type('Ego', (), {'id': 7})()
            with self.assertRaisesRegex(ValueError, 'Native target failed'):
                execute_marked_turn(world, object(), ego, 'marked-turn-case', p, digest,
                                    'indicated_course',
                                    lambda x, y, z, yaw: Transform(x, y),
                                    Recorder(), camera_factory=Cameras, drive=failing_drive)
            self.assertEqual(released, ['cameras', 'recorder'])
            self.assertTrue(world.actors[0].destroyed)


if __name__ == '__main__':
    unittest.main()
