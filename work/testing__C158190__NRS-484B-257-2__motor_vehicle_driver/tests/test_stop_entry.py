import importlib.util
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("stop_entry_measurements", ROOT / "stop_entry_measurements.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
import runner


class StopEntryTests(unittest.TestCase):
    def test_authored_stop_site_and_case_staging_plans(self):
        receipt = runner.validate_authored_site()
        self.assertEqual(receipt['approach_road_id'], 158190)
        self.assertEqual(receipt['approach_lane_id'], -1)
        self.assertEqual(receipt['stop_signal_id'], '1581902')
        prefix = runner.PREFIX
        inside = runner.plan_case(prefix + 'stop_other_inside')
        approaching = runner.plan_case(prefix + 'stop_other_approaching')
        clear = runner.plan_case(prefix + 'stop_no_other')
        rolling = runner.plan_case(prefix + 'stop_no_halt')
        self.assertEqual(inside['other_start_road_id'], 158195)
        self.assertEqual(approaching['other_start_road_id'], 158194)
        self.assertIsNone(clear['other_point_xy_m'])
        self.assertTrue(rolling['rolling_response_requested'])
        self.assertEqual(inside['ego_point_xy_m'], approaching['ego_point_xy_m'])
        with self.assertRaisesRegex(ValueError, 'different control construction'):
            runner.plan_case(prefix + 'signal_control_exception')

    def test_mutated_authored_stop_control_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'wrong-sign.xodr'
            path.write_text(runner.ROAD.read_text().replace('type="206"', 'type="205"'))
            with self.assertRaisesRegex(ValueError, 'Stop sign does not govern'):
                runner.validate_authored_site(path)

    def test_stop_stage_holds_until_observed_stillness_and_clear_path(self):
        prefix = runner.PREFIX
        stage = runner.StopStage(prefix + 'stop_other_inside', hold_frames=2)
        state = dict(before_reference=True, within_intersection=False,
                     other_clear=False)
        self.assertEqual(stage.target(2, 1, **state), 0)
        self.assertEqual(stage.target(2, 0, **state), 0)
        self.assertEqual(stage.target(2, 0, **state), 0)
        self.assertEqual(stage.stopped_frames, 2)
        self.assertEqual(stage.target(2, 0, before_reference=True,
                                      within_intersection=False, other_clear=True), 5)
        self.assertTrue(stage.released)
        rolling = runner.StopStage(prefix + 'stop_no_halt')
        self.assertEqual(rolling.target(2, 3, **state), 4)
        self.assertFalse(rolling.released)
        with self.assertRaisesRegex(ValueError, 'crossed stop reference'):
            runner.StopStage(prefix + 'stop_no_other').target(
                0, 3, before_reference=False, within_intersection=False,
                other_clear=True)

    def test_native_stop_control_inventory_rejects_stale_identity(self):
        point = SimpleNamespace(x=1, y=2, z=3)
        transform = SimpleNamespace(location=point)

        class Trigger:
            def get_world_vertices(self, value):
                self.assert_transform = value
                return [point] * 4

        class Actor:
            id = 25
            type_id = 'traffic.stop'
            trigger_volume = Trigger()

            def get_transform(self):
                return transform

        actor = Actor()
        road_map = SimpleNamespace(name='authored-stop-site',
                                   get_crosswalks=lambda: [point])
        world = SimpleNamespace(get_snapshot=lambda: SimpleNamespace(frame=50),
                                get_actors=lambda: [actor],
                                get_map=lambda: road_map)
        row = runner.observe_stop_control(world, 25, frame=50)
        self.assertEqual(row['stop_sign']['actor_id'], 25)
        self.assertEqual(len(row['stop_sign']['trigger_vertices_m']), 4)
        with self.assertRaisesRegex(ValueError, 'frame differs'):
            runner.observe_stop_control(world, 25, frame=49)
        with self.assertRaisesRegex(ValueError, 'disappeared'):
            runner.observe_stop_control(world, 26, frame=50)

    def test_runner_cpu_config_and_exact_capture_profile(self):
        config = json.loads((ROOT / 'config.json').read_text())
        self.assertEqual(runner.validate_config(config)['selected_case_id'],
                         runner.PREFIX + 'stop_other_inside')
        self.assertEqual(runner.CAMERAS,
                         ('overview', 'approach', 'reference_corner', 'driver_reference'))
        bad = dict(config, rate_hz=10)
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            runner.validate_config(bad)
        bad = dict(config, required_atoms=['ru.subject'])
        with self.assertRaisesRegex(ValueError, 'atom omitted'):
            runner.validate_config(bad)

    def fixture(self, root):
        context = {"native_map_id":"TownX", "intersection_id":42,"ego_approach_road_id":7,
                   "native_stop_sign_id":25,"sign_governance_source":"Native-trigger-and-face",
                   "entrance_inventory_source":"all-entrances-map-and-cameras",
                   "stop_reference_source":"stop-line-original-frame",
                   "highway_status_source":"road-review", "non_through_highway":True,
                   "police_control":False,"traffic_signal_control":False,
                   "ego_entrance_device":"stop",
                   "entrances":[{"road_id":7,"device":"stop"},{"road_id":9,"device":"none"}]}
        (root/"intersection_context.json").write_text(json.dumps(context))
        rows=[]
        for i,(speed,entry,before,other) in enumerate(((3,False,True,False),(0,False,True,True),(2,True,False,True))):
            x = (-14.0, -13.0, -7.0)[i]
            body = [[x+dx, dy, z] for dx in (-1.0, 1.0)
                    for dy in (-.7, .7) for z in (0.0, 1.5)]
            rows.append({"frame":100+i,"time_s":1+i*.05,"ego_road_id":7,
                         "ego":{"body_vertices_m":body},
                         "ego_speed_source":"actor.get_velocity","ego_speed_mps":speed,
                         "ego_body_in_intersection":entry,"ego_body_before_stop_reference":before,
                         "other_body_in_intersection":other,
                         "other_center_m":[1.8,4.0-float(i),0.25] if other else None,
                         "other_speed_mps":7.0 if other else None})
        frames=[{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"]} for i,r in enumerate(rows)]
        (root/"entry_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_stopped_before_entry_with_other_inside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=module.analyze(root)
            self.assertTrue(result["observed_full_stop_before_reference"])
            self.assertTrue(result["observed_other_occupancy"])
            self.assertEqual(result["legal_conclusion"],"unresolved")

    def test_occupied_intersection_requires_other_source_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = root / 'entry_history.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[1]['other_center_m'] = None
            rows[1]['other_speed_mps'] = None
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'source position'):
                module.analyze(root)

    def test_crossing_road_join_and_off_route_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            context = json.loads((root / 'intersection_context.json').read_text())
            context['ego_route_road_ids'] = [7, 8, 10]
            (root / 'intersection_context.json').write_text(json.dumps(context))
            rows = [json.loads(line) for line in (root / 'entry_history.jsonl').read_text().splitlines()]
            rows[-1]['ego_road_id'] = 8
            (root / 'entry_history.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
            self.assertEqual(module.analyze(root)['first_ego_entry_frame'], 102)
            rows[-1]['ego_road_id'] = 99
            (root / 'entry_history.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
            with self.assertRaisesRegex(ValueError, 'route identity'):
                module.analyze(root)

    def test_unsourced_exception_and_stale_frame_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            context=json.loads((root/"intersection_context.json").read_text())
            context["police_control"]=True
            (root/"intersection_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError,"exception"):
                module.analyze(root)
            self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):
                module.analyze(root)

    def test_hash_bound_review_overlay_and_mutated_camera_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            original = json.loads((root / 'intersection_context.json').read_text())
            original.update(non_through_highway=None, police_control=None,
                            traffic_signal_control=None)
            original['entrances'][1]['device'] = 'unreviewed'
            (root / 'intersection_context.json').write_text(json.dumps(original))
            for name in ('stop_control_inventory.jsonl', 'overview.mkv',
                         'approach.mkv', 'reference_corner.mkv',
                         'driver_reference.mkv'):
                (root / name).write_bytes(('diagnostic ' + name).encode())
            hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                      for name in module.REVIEW_SOURCES}
            review = {'format': 'worker-stop-context-review',
                      'reviewer': 'diagnostic-test-reviewer',
                      'method': 'CPU schema fixture only; no physical acceptance',
                      'source_hashes': hashes,
                      'findings': {
                          'native_map_id': 'TownX', 'native_stop_sign_id': 25,
                          'stop_sign_face_legible': True,
                          'stop_reference_kind': 'stop_line',
                          'stop_reference_source': 'diagnostic-source-fixture',
                          'non_through_highway': True,
                          'police_control': False, 'traffic_signal_control': False,
                          'entrances': [{'road_id': 7, 'device': 'stop'},
                                        {'road_id': 9, 'device': 'none'}]}}
            (root / 'stop_context_review.json').write_text(json.dumps(review))
            report = module.analyze(root)
            self.assertTrue(report['observed_full_stop_before_reference'])
            self.assertIn('stop_context_review.json', report['sources'])
            (root / 'overview.mkv').write_bytes(b'tampered diagnostic camera')
            with self.assertRaisesRegex(ValueError, 'source hashes'):
                module.analyze(root)

    def test_saved_finalizer_writes_diagnostic_channels_without_legal_claim(self):
        self.assertIn('.runtime-work/', os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            original = json.loads((root / 'intersection_context.json').read_text())
            original.update(non_through_highway=None, police_control=None,
                            traffic_signal_control=None)
            original['entrances'][1]['device'] = 'unreviewed'
            (root / 'intersection_context.json').write_text(json.dumps(original))
            for name in ('stop_control_inventory.jsonl', 'overview.mkv',
                         'approach.mkv', 'reference_corner.mkv',
                         'driver_reference.mkv'):
                (root / name).write_bytes(('diagnostic ' + name).encode())
            hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                      for name in module.REVIEW_SOURCES}
            review = {'format': 'worker-stop-context-review',
                      'reviewer': 'diagnostic-test-reviewer',
                      'method': 'CPU schema fixture only; no physical acceptance',
                      'source_hashes': hashes,
                      'findings': {
                          'native_map_id': 'TownX', 'native_stop_sign_id': 25,
                          'stop_sign_face_legible': True,
                          'stop_reference_kind': 'stop_line',
                          'stop_reference_source': 'diagnostic-source-fixture',
                          'non_through_highway': True,
                          'police_control': False, 'traffic_signal_control': False,
                          'entrances': [{'road_id': 7, 'device': 'stop'},
                                        {'road_id': 9, 'device': 'none'}]}}
            (root / 'stop_context_review.json').write_text(json.dumps(review))
            (root / 'config.json').write_text((ROOT / 'config.json').read_text())
            (root / 'trace.jsonl').write_text(''.join(
                json.dumps({'frame': 100 + i, 'time_s': 1 + i * .05,
                            'position_m': [float(i), 0, 0]}) + '\n'
                for i in range(3)))
            capture = root / 'capture'
            capture.mkdir()
            (capture / 'evidence.jsonl').write_text('{}\n')
            (capture / 'native_map_facts.json').write_text('{}\n')
            output = root / 'analysis.json'
            report = module.finalize(root, output)
            self.assertEqual(report['legal_conclusion'], 'unresolved')
            from worker_exchange.measurement_contract import verify_report
            contract = json.loads((ROOT / 'measurement-contract.json').read_text())
            measured = verify_report(contract, report, root)
            self.assertEqual(len(measured), 5)
            self.assertTrue(measured['full_stop_before_entry']['value'])
            self.assertEqual(len(measured['approaching_hazard_context']['value']
                                 ['other_approach_samples']), 2)
            self.assertEqual(len((root / 'channels/ego_speed_and_stop_reference.jsonl')
                                 .read_text().splitlines()), 3)
            result = json.loads((root / 'result.json').read_text())
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertTrue(result['target_checks'][0]['matched'])


if __name__ == "__main__":
    unittest.main()
