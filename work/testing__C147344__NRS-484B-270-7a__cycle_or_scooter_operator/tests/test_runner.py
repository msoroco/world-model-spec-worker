"""Original source packet and 20 Hz Native adapter contract checks."""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import SOURCE_FIELDS, VIEWS, capture, load_scene
from test_interference import Adapter, scene_for
from interference import CASES


def reviewed_packet(root, case):
    scene = scene_for(case)
    sources = {}
    contents = {
        'electric_bicycle_classification': scene['electric_bicycle'],
        'motor_vehicle_classification': scene['motor_vehicle'],
        'route_geometry': {'routes': scene['routes'],
                           'lane_assignments': scene['lane_assignments']},
        'operator_control': {'bicycle_path': scene['bicycle_path'],
                             'motor_response': scene['motor_response']}}
    for field in SOURCE_FIELDS:
        name = field + '.txt'
        if field == 'reviewed_road':
            (root / name).write_text('reviewed-road\n')
        elif field == 'authored_plan':
            # Source bytes are sealed before the scene binds their digest.
            declaration = scene['intention_declaration']
            if declaration is not None:
                declaration = {key: value for key, value in declaration.items()
                               if key != 'source_sha256'}
            (root / name).write_text(json.dumps(declaration) + '\n')
        else:
            (root / name).write_text(json.dumps(contents[field]) + '\n')
        digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
        scene[field + '_source_sha256'] = digest
        sources[field] = {'path': name, 'sha256': digest}
    if scene['intention_declaration'] is not None:
        scene['intention_declaration']['source_sha256'] = (
            scene['authored_plan_source_sha256'])
        # The declaration's own digest field cannot be embedded in the file
        # whose digest it names, so content comparison omits that field.
    packet = {'format': 'c147344-reviewed-original-scene-v1',
              'case_id': 'testing__C147344__NRS-484B-270-7a__cycle_or_scooter_operator__' +
                         case.suffix,
              'scene': scene, 'sources': sources}
    path = root / 'scene-packet.json'
    path.write_text(json.dumps(packet) + '\n')
    return path, scene


class NativeAdapter(Adapter):
    def __init__(self, road):
        super().__init__()
        self.road = road
        self.frames = 0

    def map_opendrive_bytes(self):
        return self.road

    def route_readback(self, routes, lanes):
        return True

    def begin_four_camera_capture(self, views, cameras, owned, output):
        self.calls.append(('camera-start', views))

    def tick(self):
        self.frames += 1
        return 1000 + self.frames

    def record_original_interaction_readback(self, frame, built, output):
        self.calls.append(('readback', frame))

    def finish_four_camera_capture(self, output):
        self.calls.append(('camera-finish', self.frames))

    def camera_frame_counts(self):
        return {name: self.frames for name in VIEWS}

    def native_source_kind(self):
        return 'original_native_capture'


class RunnerTest(unittest.TestCase):
    def test_reviewed_packet_positive_and_changed_source_negative(self):
        scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            packet, scene = reviewed_packet(root, CASES[0])
            loaded, digest = load_scene(packet, root, CASES[0])
            self.assertEqual(loaded['bicycle_id'], scene['bicycle_id'])
            self.assertEqual(len(digest), 64)
            (root / 'authored_plan.txt').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'source hash changed'):
                load_scene(packet, root, CASES[0])

    def test_capture_calls_original_readback_and_restores_actors(self):
        scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            packet, _ = reviewed_packet(root, CASES[0])
            scene, digest = load_scene(packet, root, CASES[0])
            road = (root / 'reviewed_road.txt').read_bytes()
            adapter = NativeAdapter(road)
            config = json.loads((Path(__file__).resolve().parents[1] /
                                 'config.json').read_text())
            config['selected_case_id'] = (
                'testing__C147344__NRS-484B-270-7a__cycle_or_scooter_operator__' +
                CASES[0].suffix)
            result = capture(adapter, scene, CASES[0], config, root, digest)
            self.assertEqual(result['frame_count'], 600)
            self.assertEqual(adapter.calls[-2:], [('destroy', 'motor'),
                                                  ('destroy', 'ebike')])
            self.assertIn(('camera-finish', 600), adapter.calls)

    def test_scene_cannot_relabel_a_hashed_motor_response_source(self):
        scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            packet, _ = reviewed_packet(root, CASES[0])
            value = json.loads(packet.read_text())
            value['scene']['motor_response'] = 'continue'
            packet.write_text(json.dumps(value) + '\n')
            with self.assertRaisesRegex(ValueError, 'source content differs'):
                load_scene(packet, root, CASES[0])

    def test_live_road_mismatch_rejected_before_spawn(self):
        scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            packet, _ = reviewed_packet(root, CASES[0])
            scene, digest = load_scene(packet, root, CASES[0])
            adapter = NativeAdapter(b'wrong road')
            config = json.loads((Path(__file__).resolve().parents[1] /
                                 'config.json').read_text())
            config['selected_case_id'] = (
                'testing__C147344__NRS-484B-270-7a__cycle_or_scooter_operator__' +
                CASES[0].suffix)
            with self.assertRaisesRegex(ValueError, 'live road differs'):
                capture(adapter, scene, CASES[0], config, root, digest)
            self.assertFalse(any(call[0] == 'bicycle' for call in adapter.calls))


if __name__ == '__main__':
    unittest.main()
