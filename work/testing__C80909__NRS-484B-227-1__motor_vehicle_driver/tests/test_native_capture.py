import importlib.util
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_capture', ROOT / 'native_capture.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


def actor(actor_id, x, y, yaw=0):
    vertices = [NS(x=x+dx, y=y+dy) for dx, dy in
                ((-1, -1), (-1, 1), (1, 1), (1, -1))]
    pose = NS(rotation=NS(yaw=yaw))
    return NS(id=actor_id, get_transform=lambda: pose,
              bounding_box=NS(get_world_vertices=lambda transform: vertices))


class CaptureTests(unittest.TestCase):
    def context(self):
        return {'native_map_id': 'TownX', 'divided_highway_source': 'reviewed-map',
                'roadway_boundaries_source': 'reviewed-road',
                'opening_geometry_source': 'reviewed-gap',
                'barrier_actors_source': 'Native-vertices',
                'other_vehicle_source': 'Native-actor',
                'right_hand_roadway_xy_m': [[0,-10],[30,-10],[30,-2],[0,-2]],
                'destination_roadway_xy_m': [[0,2],[30,2],[30,10],[0,10]],
                'dividing_space_xy_m': [[0,-2],[30,-2],[30,2],[0,2]],
                'opening_xy_m': [[10,-2],[20,-2],[20,2],[10,2]]}

    def test_four_native_sensors_and_original_tick_sources(self):
        made = []
        class Sensor:
            def __init__(self): self.callback = None; self.stopped = False; self.destroyed = False
            def listen(self, callback): self.callback = callback
            def stop(self): self.stopped = True
            def destroy(self): self.destroyed = True
        def spawn(blueprint, transform, **kwargs):
            sensor = Sensor()
            made.append((dict(blueprint.attributes), transform, kwargs, sensor))
            return sensor
        class Blueprint:
            def __init__(self): self.attributes = {}
            def set_attribute(self, key, value): self.attributes[key] = value
        world = NS(get_blueprint_library=lambda: NS(find=lambda name: Blueprint()),
                   spawn_actor=spawn)
        ego, other = actor(1, 15, -5), actor(2, 26, -5)
        transforms = {name: name + '-pose' for name in capture.CAMERAS}
        with capture.original_cameras(world, ego, transforms, timeout_s=.01) as read:
            self.assertEqual(len(made), 4)
            self.assertEqual(made[-1][2], {'attach_to': ego})
            self.assertEqual([entry[2] for entry in made[:3]], [{}, {}, {}])
            self.assertEqual([entry[0]['sensor_tick'] for entry in made], ['0.05']*4)
            for name, (_, _, _, sensor) in zip(capture.CAMERAS, made):
                width, height = capture.CAMERAS[name]
                sensor.callback(NS(frame=10, width=width, height=height))
            images = read(10)
            movement, frames = io.StringIO(), io.StringIO()
            written = []
            writers = {name: lambda image, name=name: written.append((name, image.frame))
                       for name in capture.CAMERAS}
            recorder = capture.OriginalTickRecorder(self.context(), movement, frames, writers)
            snapshot = NS(frame=10, timestamp=NS(elapsed_seconds=.5))
            row = recorder.record(snapshot, ego, other, images)
            self.assertEqual(len(written), 4)
            self.assertEqual(row['ego_actor_id'], 1)
            self.assertEqual(len(row['ego_body_vertices_xy_m']), 4)
            self.assertEqual(json.loads(frames.getvalue())['carla_frame'], 10)
            with self.assertRaisesRegex(ValueError, 'Nonmonotone'):
                recorder.record(snapshot, ego, other, images)
            snapshot.frame = 11
            snapshot.timestamp.elapsed_seconds = .55
            with self.assertRaisesRegex(ValueError, 'join Native tick'):
                recorder.record(snapshot, ego, other, images)
        self.assertTrue(all(entry[3].stopped and entry[3].destroyed for entry in made))

    def test_source_and_camera_fail_closed(self):
        bad = self.context()
        bad['opening_xy_m'] = [[31,-2],[33,-2],[33,2],[31,2]]
        with self.assertRaisesRegex(ValueError, 'outside reviewed divider'):
            capture.OriginalTickRecorder(bad, io.StringIO(), io.StringIO(),
                                         {name: lambda image: None for name in capture.CAMERAS})
        with self.assertRaisesRegex(ValueError, 'Four camera poses'):
            with capture.original_cameras(None, None, {'overview': None}): pass


if __name__ == '__main__': unittest.main()
