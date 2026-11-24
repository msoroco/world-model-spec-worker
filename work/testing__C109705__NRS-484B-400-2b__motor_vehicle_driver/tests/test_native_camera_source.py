import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_camera_source import CAMERAS, NativeCameraSource
from test_native_capture import Adapter, CASE, native
from test_construction import survey


class Sensor:
    def __init__(self, sensor_id):
        self.id = sensor_id
        self.callback = None
        self.stopped = self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.sensors = []
        self.blueprints = []

    def get_blueprint_library(self):
        return self

    def find(self, name):
        if name != 'sensor.camera.rgb':
            raise ValueError(name)
        blueprint = SimpleNamespace(attributes={})
        blueprint.set_attribute = blueprint.attributes.__setitem__
        self.blueprints.append(blueprint)
        return blueprint

    def spawn_actor(self, blueprint, transform, *, attach_to):
        sensor = Sensor(len(self.sensors) + 10)
        self.sensors.append(sensor)
        return sensor


class CameraSourceTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[3] / '.runtime-work' / 'c109705-camera-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = World()
        self.carla = SimpleNamespace(
            Location=lambda **kw: SimpleNamespace(**kw),
            Rotation=lambda **kw: SimpleNamespace(**kw),
            Transform=lambda location, rotation: SimpleNamespace(location=location, rotation=rotation))
        self.survey = {'cell_id': 'C109705', 'maneuver': 'left_turn',
                       'camera_poses': {name: {'x': 0.0, 'y': 0.0, 'z': 2.0,
                                             'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0}
                                         for name in CAMERAS}}

    def source(self):
        survey_path = self.root / 'camera-survey.json'
        raw = (json.dumps(self.survey) + '\n').encode()
        survey_path.write_bytes(raw)
        source = NativeCameraSource(self.world, self.carla, survey_path,
                                    hashlib.sha256(raw).hexdigest(),
                                    self.root / 'camera_sources',
                                    dimensions={name: (2, 2) for name in CAMERAS},
                                    timeout_s=.01)
        self.addCleanup(source.close)
        return source

    def test_original_callback_png_hashes_and_owned_cleanup(self):
        source = self.source()
        source.configure_cameras(object(), CAMERAS, fps=20)
        self.assertEqual(len(self.world.sensors), 4)
        self.assertEqual(self.world.blueprints[0].attributes['sensor_tick'], '0.05')
        for sensor in self.world.sensors:
            def save(path, value=sensor.id):
                Image.new('RGB', (2, 2), (value, 0, 0)).save(path)
            sensor.callback(SimpleNamespace(frame=42, width=2, height=2,
                                            save_to_disk=save))
        for name in CAMERAS:
            row = source.camera_frame(name, 42)
            path = self.root / row['source_path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row['source_sha256'])
            with Image.open(path) as image:
                self.assertEqual(image.size, (2, 2))
        source.close()
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in self.world.sensors))

    def test_missing_stale_and_overwrite_rejected(self):
        source = self.source()
        source.configure_cameras(object(), CAMERAS, fps=20)
        with self.assertRaisesRegex(ValueError, 'callback absent'):
            source.camera_frame('dash', 42)
        self.world.sensors[0].callback(SimpleNamespace(frame=41, width=2, height=2))
        with self.assertRaisesRegex(ValueError, 'frame mismatch'):
            source.camera_frame('dash', 42)

    def test_unsurveyed_pose_rejected_without_partial_actors(self):
        self.survey['camera_poses'].pop('left')
        with self.assertRaisesRegex(ValueError, 'source-surveyed'):
            self.source()
        self.assertFalse(self.world.sensors)

    def test_changed_original_survey_packet_rejected(self):
        survey_path = self.root / 'camera-survey.json'
        survey_path.write_text(json.dumps(self.survey) + '\n')
        with self.assertRaisesRegex(ValueError, 'survey packet hash differs'):
            NativeCameraSource(self.world, self.carla, survey_path, '0' * 64,
                               self.root / 'camera_sources')
        self.assertFalse(self.world.sensors)

    def test_native_capture_uses_owned_camera_source_and_closes_on_failure(self):
        class Source:
            def __init__(self):
                self.configured = self.closed = False

            def configure_cameras(self, ego, channels, *, fps):
                self.configured = tuple(channels) == CAMERAS and fps == 20

            def camera_frame(self, channel, frame):
                if channel == 'right' and frame == 10:
                    raise ValueError('original callback absent')
                return {'channel': channel, 'frame': frame,
                        'source_path': f'camera_sources/{channel}/{frame}.png',
                        'source_sha256': 'a' * 64}

            def close(self):
                self.closed = True

        map_path = self.root / 'original-map.xodr'
        map_path.write_text('<OpenDRIVE/>\n')
        selected = survey()
        selected['source_sha256'] = hashlib.sha256(map_path.read_bytes()).hexdigest()
        adapter = Adapter()
        source = Source()
        source.output = self.root / 'attempt' / 'camera_sources'
        with self.assertRaisesRegex(ValueError, 'original callback absent'):
            native.capture(adapter, CASE, selected, map_path,
                           self.root / 'attempt', camera_source=source)
        self.assertTrue(source.configured and source.closed)
        self.assertTrue(adapter.stopped and adapter.destroyed)


if __name__ == '__main__':
    unittest.main()
