from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_scene import build_scene, destroy_scene
from runner import PREFIX, _abreast, check_config
from overtake_finalizer import analyze, build_result
from overtake_camera import CAMERAS, OvertakeCameraCapture
from test_overtake_route import lanes
from test_overtake_sequence import source
import json
import tempfile


class SceneTests(unittest.TestCase):
    def test_four_source_camera_creation_and_missing_frame_rejection(self):
        sensors = []
        class Sensor:
            def listen(self, callback):
                self.callback = callback
            def stop(self):
                pass
            def destroy(self):
                self.destroyed = True
        def spawn(_blueprint, _transform, attach_to):
            self.assertIs(attach_to, ego)
            sensor = Sensor()
            sensors.append(sensor)
            return sensor
        ego = object()
        blueprint = NS(set_attribute=lambda *_: None)
        world = NS(get_blueprint_library=lambda: NS(find=lambda _: blueprint),
                   spawn_actor=spawn)
        carla = NS(Location=lambda *parts: parts, Rotation=lambda *parts: parts,
                   Transform=lambda location, rotation: (location, rotation))
        sinks = {name: NS(write=lambda image: None) for name in CAMERAS}
        capture = OvertakeCameraCapture(world, carla, ego, sinks)
        self.assertEqual(len(sensors), 4)
        for sensor, (name, spec) in zip(sensors, CAMERAS.items()):
            width, height = spec[2]
            sensor.callback(NS(frame=20, width=width, height=height))
        capture.wait_for_frame(20, timeout_s=.01)
        self.assertEqual(capture.verify([20]), {name: 1 for name in CAMERAS})
        with self.assertRaisesRegex(ValueError, 'Missing or extra'):
            capture.verify([20, 21])
        capture.close()
        self.assertTrue(all(sensor.destroyed for sensor in sensors))

    def test_saved_finalizer_joins_original_sources_and_rejects_missing_body(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {'selected_case_id': PREFIX + 'return_before_clear',
                      'law_id': 'NRS-484B-207-1', 'cell_id': 'C229126',
                      'actor': 'motor_vehicle_driver', 'target_left_gap_m': 1.0,
                      'requested_return_clearance_m': -.5, 'rate_hz': 20,
                      'frames': 320, 'duration_s': 16,
                      'camera_names': ['overview', 'approach', 'reference_corner',
                                       'driver_reference'],
                      'supported_case_ids': [PREFIX + 'return_before_clear'],
                      'case': {'recording_description': {'purpose': 'CPU source test'}}}
            (root / 'config.json').write_text(json.dumps(config))
            bodies = source(early=True)
            (root / 'participant_footprints.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in bodies))
            mapping = [{'video_frame': i, 'carla_frame': row['frame'],
                        'time_s': row['time_s']} for i, row in enumerate(bodies)]
            (root / 'video_frames.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in mapping))
            trace = [{'frame': row['frame'], 'time_s': row['time_s']}
                     for row in bodies]
            (root / 'trace.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in trace))
            report = analyze(root)
            result = build_result(root, report)
            sys.path.insert(0, str(Path(__file__).resolve().parents[3] /
                                   'runtime' / 'scenario_pipeline'))
            from worker_exchange.native_output import validate_result
            validate_result(result)
            self.assertEqual(result['case_id'], config['selected_case_id'])
            self.assertEqual(len(result['recording_evidence']), 2)
            self.assertFalse(result['physical_acceptance_claimed'])
            (root / 'participant_footprints.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required original source'):
                analyze(root)

    def test_exact_runner_identity_and_camera_contract(self):
        config = {'selected_case_id': PREFIX + 'return_before_clear',
                  'law_id': 'NRS-484B-207-1', 'cell_id': 'C229126',
                  'actor': 'motor_vehicle_driver', 'target_left_gap_m': 1.0,
                  'requested_return_clearance_m': -.5, 'rate_hz': 20,
                  'frames': 320, 'duration_s': 16,
                  'camera_names': ['overview', 'approach', 'reference_corner',
                                   'driver_reference'],
                  'supported_case_ids': [PREFIX + 'return_before_clear']}
        self.assertEqual(check_config(config), 'return_before_clear')
        with self.assertRaisesRegex(ValueError, 'Four named'):
            check_config({**config, 'camera_names': ['overview']})
        with self.assertRaisesRegex(ValueError, 'controls changed'):
            check_config({**config, 'requested_return_clearance_m': 1.5})

    def test_abreast_uses_original_full_body_and_left_position(self):
        row = {'road_tangent_xy': [1, 0],
               'ego_corners': [[3, 2], [5, 2], [5, 3], [3, 3]],
               'other_corners': [[3, 0], [5, 0], [5, 1], [3, 1]]}
        self.assertTrue(_abreast(row))
        self.assertFalse(_abreast({**row, 'ego_corners': [[6, 2], [8, 2],
                                                          [8, 3], [6, 3]]}))

    def test_spawn_from_connected_same_direction_route(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                world_map, right, _ = lanes(direction)
                spawned = []
                def spawn(blueprint, transform):
                    actor = NS(id=len(spawned) + 1, transform=transform,
                               destroyed=False)
                    actor.destroy = lambda actor=actor: setattr(actor, 'destroyed', True)
                    spawned.append(actor)
                    return actor
                world = NS(get_map=lambda: world_map,
                           get_blueprint_library=lambda: NS(find=lambda _: 'vehicle'),
                           try_spawn_actor=spawn)
                scene = build_scene(world)
                self.assertIs(scene['other'].transform, right[8].transform)
                self.assertIs(scene['ego'].transform, right[0].transform)
                destroy_scene(scene)
                self.assertTrue(all(actor.destroyed for actor in spawned))

    def test_failed_second_spawn_restores_first_actor(self):
        world_map, _, _ = lanes()
        actor = NS(id=1, destroyed=False)
        actor.destroy = lambda: setattr(actor, 'destroyed', True)
        calls = []
        def spawn(*_):
            calls.append(1)
            return actor if len(calls) == 1 else None
        world = NS(get_map=lambda: world_map,
                   get_blueprint_library=lambda: NS(find=lambda _: 'vehicle'),
                   try_spawn_actor=spawn)
        with self.assertRaisesRegex(ValueError, 'subject spawn failed'):
            build_scene(world)
        self.assertTrue(actor.destroyed)


if __name__ == '__main__':
    unittest.main()
