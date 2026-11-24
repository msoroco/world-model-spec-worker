import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import CAMERAS, FrameJoin, FourCameraCapture
from native_run import configure_world, source_configuration, snapshot_sources, spawn_case_pedestrian, pedestrian_source
from delivery_audit import audit_source_provenance

CASE = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator__reference"


class NativeAdapterTests(unittest.TestCase):
    def test_four_source_frame_join_and_gap(self):
        join = FrameJoin()
        images = {name: SimpleNamespace(frame=100) for name in CAMERAS}
        self.assertEqual(join.accept(100, 0.05, images)["video_frame"], 0)
        for name in CAMERAS:
            images[name] = SimpleNamespace(frame=101)
        self.assertEqual(join.accept(101, 0.10, images)["video_frame"], 1)
        images["approach"] = SimpleNamespace(frame=99)
        with self.assertRaisesRegex(ValueError, "do not match"):
            join.accept(102, 0.15, images)
        images["approach"] = SimpleNamespace(frame=103)
        with self.assertRaisesRegex(ValueError, "do not match"):
            join.accept(102, 0.15, images)
        images = {name: SimpleNamespace(frame=103) for name in CAMERAS}
        with self.assertRaisesRegex(ValueError, "discontinuity"):
            join.accept(103, 0.20, images)

    def test_hash_bound_native_sources_and_classification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            road = root / 'road.xodr'
            road.write_text('<OpenDRIVE/>\n')
            digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            packets = {
                'municipal': {'source_kind': 'reviewed_original', 'reviewed_by': 'CPU test reviewer',
                              'city_of_las_vegas': True, 'world_map': 'local',
                              'map_sha256': digest(road)},
                'bicycle': {'source_kind': 'reviewed_original', 'reviewed_by': 'CPU test reviewer',
                            'human_powered': True, 'moped': False, 'blueprint_id': 'vehicle.bicycle'},
                'rack': {'source_kind': 'reviewed_original', 'reviewed_by': 'CPU test reviewer',
                         'rack_type': 'bicycle_rack', 'blueprint_id': 'static.rack'}}
            refs = {}
            for name, packet in packets.items():
                path = root / (name + '.json')
                path.write_text(json.dumps(packet))
                refs[name] = {'path': str(path), 'sha256': digest(path)}
            scene = {"case_id": CASE, "world_map": "local", "map_sha256": digest(road),
                     'road_source': {'path': str(road), 'sha256': digest(road)},
                     'bicycle_blueprint_id': 'vehicle.bicycle', 'rack_blueprint_id': 'static.rack',
                     "human_powered_bicycle_verified": True, "rack_asset_verified": True,
                     "bicycle_classification_source": refs['bicycle'],
                     "rack_geometry_source": refs['rack'],
                     "jurisdiction": {"city_of_las_vegas": True, "source": refs['municipal']}}
            assets = {"source_kind": "original_local_native_blueprint_inventory",
                      "world_map": "local", "blueprint_ids": ["vehicle.bicycle", "static.rack",
                                                           "walker.pedestrian.0001"]}
            sp = root / "scene.json"
            ap = root / "assets.json"
            sp.write_text(json.dumps(scene))
            ap.write_text(json.dumps(assets))
            env = {"C10307_SCENE_SOURCE": str(sp), "C10307_SCENE_SHA256": digest(sp),
                   "C10307_ASSET_INVENTORY": str(ap), "C10307_ASSET_SHA256": digest(ap)}
            selected, inventory = source_configuration(env, CASE)
            self.assertEqual(selected, scene)
            self.assertEqual(inventory, assets)
            attempt = root / 'attempt'
            attempt.mkdir()
            snapshot_sources(attempt, env, selected, CASE)
            receipt = audit_source_provenance(attempt, CASE)
            self.assertEqual(receipt['source_sha256']['road'], digest(road))
            missing_asset_path = root / 'missing-rack-assets.json'
            missing_asset_path.write_text(json.dumps({**assets,
                'blueprint_ids': ['vehicle.bicycle']}))
            missing_asset_env = {**env, 'C10307_ASSET_INVENTORY': str(missing_asset_path),
                                 'C10307_ASSET_SHA256': digest(missing_asset_path)}
            with self.assertRaisesRegex(ValueError, 'blueprint inventory differs'):
                source_configuration(missing_asset_env, CASE)
            missing_asset_attempt = root / 'missing-rack-attempt'
            missing_asset_attempt.mkdir()
            snapshot_sources(missing_asset_attempt, missing_asset_env, scene, CASE)
            with self.assertRaisesRegex(ValueError, 'blueprint inventory mismatch'):
                audit_source_provenance(missing_asset_attempt, CASE)
            wrong_map = {**packets['municipal'], 'map_sha256': '0' * 64}
            wrong_map_path = root / 'wrong-map-municipal.json'
            wrong_map_path.write_text(json.dumps(wrong_map))
            wrong_scene = {**scene, 'jurisdiction': {'city_of_las_vegas': True,
                            'source': {'path': str(wrong_map_path),
                                       'sha256': digest(wrong_map_path)}}}
            wrong_scene_path = root / 'wrong-map-scene.json'
            wrong_scene_path.write_text(json.dumps(wrong_scene))
            wrong_env = {**env, 'C10307_SCENE_SOURCE': str(wrong_scene_path),
                         'C10307_SCENE_SHA256': digest(wrong_scene_path)}
            with self.assertRaisesRegex(ValueError, 'municipal jurisdiction packet differs'):
                source_configuration(wrong_env, CASE)
            wrong_attempt = root / 'wrong-map-attempt'
            wrong_attempt.mkdir()
            snapshot_sources(wrong_attempt, wrong_env, wrong_scene, CASE)
            with self.assertRaisesRegex(ValueError, 'classification mismatch'):
                audit_source_provenance(wrong_attempt, CASE)
            near_case = CASE.replace('__reference', '__pedestrian_near_rack')
            pedestrian_path = root / 'pedestrian.json'
            pedestrian_path.write_text(json.dumps({
                'source_kind': 'reviewed_original', 'reviewed_by': 'CPU test reviewer',
                'case_id': near_case, 'blueprint_id': 'walker.pedestrian.0001',
                'rack_blueprint_id': 'static.rack',
                'spawn_pose': {'x': .5, 'y': 3.5, 'z': .2, 'yaw': 90.0}}))
            near_scene = {**scene, 'case_id': near_case,
                          'pedestrian_blueprint_id': 'walker.pedestrian.0001',
                          'pedestrian_spawn_source': {'path': str(pedestrian_path),
                                                      'sha256': digest(pedestrian_path)}}
            near_scene_path = root / 'near-scene.json'
            near_scene_path.write_text(json.dumps(near_scene))
            near_env = {**env, 'C10307_SCENE_SOURCE': str(near_scene_path),
                        'C10307_SCENE_SHA256': digest(near_scene_path)}
            selected_near, _ = source_configuration(near_env, near_case)
            near_attempt = root / 'near-attempt'
            near_attempt.mkdir()
            snapshot_sources(near_attempt, near_env, selected_near, near_case)
            near_receipt = audit_source_provenance(near_attempt, near_case)
            self.assertEqual(near_receipt['source_sha256']['pedestrian'], digest(pedestrian_path))
            (near_attempt / 'source-provenance' / 'pedestrian.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                audit_source_provenance(near_attempt, near_case)
            (attempt / 'source-provenance' / 'rack.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                audit_source_provenance(attempt, CASE)
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                snapshot_sources(attempt, env, selected, CASE)
            packets['municipal']['city_of_las_vegas'] = False
            (root / 'municipal.json').write_text(json.dumps(packets['municipal']))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                source_configuration(env, CASE)
            (root / 'municipal.json').write_text(json.dumps({**packets['municipal'],
                                                           'city_of_las_vegas': True}))
            road.write_text('<OpenDRIVE changed="yes"/>\n')
            with self.assertRaisesRegex(ValueError, 'case/map source mismatch'):
                source_configuration(env, CASE)
            road.write_text('<OpenDRIVE/>\n')
            scene["human_powered_bicycle_verified"] = False
            sp.write_text(json.dumps(scene))
            env["C10307_SCENE_SHA256"] = digest(sp)
            with self.assertRaisesRegex(ValueError, "classification"):
                source_configuration(env, CASE)
            env["C10307_SCENE_SHA256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                source_configuration(env, CASE)

    def test_world_settings_and_weather_readback(self):
        class World:
            def __init__(self):
                self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None, no_rendering_mode=True)
                self.weather = SimpleNamespace(fog_density=2.0, wetness=0.0, precipitation=0.0)
            def get_settings(self): return self.settings
            def apply_settings(self, value): self.settings = value
            def get_weather(self): return self.weather
            def set_weather(self, value): self.weather = value
        world = World()
        config = {"case": {"world_setup": {"visibility_condition": "reduced", "surface_condition": "wet"}}}
        configure_world(world, config)
        self.assertTrue(world.settings.synchronous_mode)
        self.assertFalse(world.settings.no_rendering_mode)
        self.assertEqual(world.weather.fog_density, 70.0)
        self.assertEqual(world.weather.wetness, 75.0)

    def test_case_pedestrian_spawn_is_source_gated(self):
        config = {"selected_case_id": CASE.replace('__reference', '__pedestrian_near_rack'),
                  "case": {"world_setup": {"pedestrian_condition": "pedestrian near rack"}}}
        with self.assertRaisesRegex(ValueError, "source"):
            spawn_case_pedestrian(None, None, {}, {"blueprint_ids": []}, config)
        config["case"]["world_setup"]["pedestrian_condition"] = "no pedestrian near rack"
        self.assertIsNone(spawn_case_pedestrian(None, None, {}, {}, config))

    def test_reviewed_pedestrian_pose_controls_spawn_and_rejects_drift(self):
        case = CASE.replace('__reference', '__pedestrian_near_rack')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pedestrian.json'
            packet = {'source_kind': 'reviewed_original', 'reviewed_by': 'CPU test reviewer',
                      'case_id': case, 'blueprint_id': 'walker.pedestrian.0001',
                      'rack_blueprint_id': 'static.rack',
                      'spawn_pose': {'x': 0.5, 'y': 3.5, 'z': 0.2, 'yaw': 90.0}}
            path.write_text(json.dumps(packet))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            scene = {'pedestrian_blueprint_id': packet['blueprint_id'],
                     'rack_blueprint_id': packet['rack_blueprint_id'],
                     'pedestrian_spawn_source': {'path': str(path), 'sha256': digest}}
            self.assertEqual(pedestrian_source(scene, case), packet)
            actor = SimpleNamespace(type_id=packet['blueprint_id'])
            blueprint = SimpleNamespace(id=packet['blueprint_id'])
            class World:
                def get_blueprint_library(self):
                    return SimpleNamespace(find=lambda _: blueprint)
                def spawn_actor(self, _, transform):
                    self.transform = transform
                    return actor
            world = World()
            carla = SimpleNamespace(Location=lambda **kwargs: kwargs,
                                    Rotation=lambda **kwargs: kwargs,
                                    Transform=lambda location, rotation: (location, rotation))
            config = {'selected_case_id': case,
                      'case': {'world_setup': {'pedestrian_condition': 'pedestrian near rack'}}}
            self.assertIs(spawn_case_pedestrian(world, carla, scene,
                          {'blueprint_ids': [packet['blueprint_id']]}, config), actor)
            self.assertEqual(world.transform[0], {'x': .5, 'y': 3.5, 'z': .2})
            self.assertEqual(world.transform[1], {'yaw': 90.0})
            packet['spawn_pose']['y'] = 20.0
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                pedestrian_source(scene, case)
            scene['pedestrian_spawn_source']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'not near rack'):
                pedestrian_source(scene, case)

    def test_four_sensor_creation_pixels_and_cleanup(self):
        class Blueprint:
            def __init__(self): self.attributes = {}
            def set_attribute(self, key, value): self.attributes[key] = value
        class Sensor:
            def __init__(self, attributes):
                self.attributes = dict(attributes)
                self.callback = None
                self.stopped = self.destroyed = False
            def listen(self, callback): self.callback = callback
            def stop(self): self.stopped = True
            def destroy(self): self.destroyed = True
        class World:
            def __init__(self): self.blueprint = Blueprint(); self.sensors = []
            def get_blueprint_library(self): return SimpleNamespace(find=lambda _: self.blueprint)
            def spawn_actor(self, blueprint, transform):
                sensor = Sensor(blueprint.attributes)
                self.sensors.append(sensor)
                return sensor
        class Encoder:
            def __init__(self): self.stdin = BytesIO(); self.bytes = 0
            def wait(self, timeout): return 0
        world = World()
        encoders = []
        def start(*args, **kwargs):
            encoder = Encoder()
            encoders.append(encoder)
            return encoder
        carla = SimpleNamespace(Location=lambda **kwargs: kwargs,
                                Rotation=lambda **kwargs: kwargs,
                                Transform=lambda *args: args)
        config = {"cameras": [{"name": name, "width": 2, "height": 2, "fov_deg": 90}
                              for name in CAMERAS]}
        with tempfile.TemporaryDirectory() as directory, patch("native_capture.subprocess.Popen", side_effect=start):
            capture = FourCameraCapture(world, carla, config, directory)
            self.assertEqual(len(world.sensors), 4)
            for sensor in world.sensors:
                sensor.callback(SimpleNamespace(frame=100, raw_data=b"\x01" * 16))
            self.assertEqual(capture.capture(100, 0.05)["video_frame"], 0)
            capture.close()
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))
            self.assertTrue(all(encoder.stdin.closed for encoder in encoders))
            lines = (Path(directory) / "video_frames.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["carla_frame"], 100)


if __name__ == "__main__":
    unittest.main()
