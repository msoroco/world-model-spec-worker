import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yield_context import CAMERAS, derive_context


class ContextTests(unittest.TestCase):
    def fixture(self, root):
        shutil.copy(ROOT / 'native-map-plan/yield-nearest-view.xodr', root / 'road.xodr')
        (root / 'capture').mkdir()
        (root / 'capture/native_map_facts.json').write_text(json.dumps({
            'map': 'yield-native', 'junctions': [{'id': 158191}],
            'crosswalk_vertices_m': []}))
        (root / 'road_context.json').write_text(json.dumps({
            'native_map_id': 'yield-native', 'intersection_id': 158191,
            'approach_road_id': 158190, 'approach_lane_id': -1,
            'through_highway_id': 158195, 'native_yield_sign_id': 12,
            'no_stop_line': None, 'no_near_crosswalk': None,
            'police_control': None, 'traffic_signal_control': None}))
        frames = [{'video_frame': i, 'carla_frame': 100 + i, 'time_s': 5 + i*.05}
                  for i in range(2)]
        (root / 'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
        controls = [{'frame': r['carla_frame'],
                     'yield_sign': {'actor_id': 12, 'blueprint': 'traffic.yield',
                                    'trigger_vertices_m': [[0,0,0]]*4},
                     'native_crosswalk_vertices_m': [], 'competing_controls': []}
                    for r in frames]
        (root / 'control_inventory.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in controls))
        for camera in CAMERAS:
            (root / camera).write_bytes(b'cpu-diagnostic-camera-source')
        review = {'method': 'original_source_camera_frame_review',
                  'reviewer': 'cpu-fixture-reviewer', 'reviewed_frame_count': 2,
                  'reviewed_carla_frames': [100, 101],
                  'first_carla_frame': 100, 'last_carla_frame': 101,
                  'source_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                                    for name in CAMERAS},
                  'yield_sign_face_visible': True, 'no_stop_line': True,
                  'no_near_crosswalk': True, 'no_police_direction': True,
                  'no_traffic_signal_control': True}
        (root / 'rendered_marking_review.json').write_text(json.dumps(review))

    def test_derives_only_after_joined_native_and_review_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            context = derive_context(root)
            self.assertTrue(context['no_stop_line'])
            self.assertFalse(context['traffic_signal_control'])
            self.assertIn('source_review_sha256', context)

    def test_rejects_changed_camera_and_competing_control(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / CAMERAS[0]).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'hashes differ'):
                derive_context(root)
            self.fixture_existing_review(root)
            rows = [json.loads(line) for line in (root/'control_inventory.jsonl').read_text().splitlines()]
            rows[1]['competing_controls'] = [{'actor_id': 88, 'blueprint': 'traffic.stop'}]
            (root/'control_inventory.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError, 'competing-control'):
                derive_context(root)

    @staticmethod
    def fixture_existing_review(root):
        review = json.loads((root/'rendered_marking_review.json').read_text())
        review['source_sha256']['overview.mkv'] = hashlib.sha256((root/'overview.mkv').read_bytes()).hexdigest()
        (root/'rendered_marking_review.json').write_text(json.dumps(review))

    def test_rejects_unreviewed_negative_fact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            review = json.loads((root/'rendered_marking_review.json').read_text())
            review['no_near_crosswalk'] = False
            (root/'rendered_marking_review.json').write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, 'not supported'):
                derive_context(root)
