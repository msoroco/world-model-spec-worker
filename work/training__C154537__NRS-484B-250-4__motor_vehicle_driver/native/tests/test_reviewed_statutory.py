import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('reviewed_statutory', ROOT / 'reviewed_statutory.py')
import sys
sys.path.insert(0, str(ROOT))
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ReviewedStatutory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        survey = {'source_kind': 'original_native', 'stop_line_present': False,
                  'near_side_crosswalk_present': False,
                  'sidewalk_derived_crosswalk_reviewed': False,
                  'signal_installed': True, 'signal_uncovered': True,
                  'signal_id': '701', 'intersection_entry_front_x_m': -6,
                  'driver_view_samples': [{'center_x_m': -9,
                                           'approaching_traffic_visible': True}]}
        (self.root / 'scene-survey.json').write_text(json.dumps(survey))
        (self.root / 'signal_context.json').write_text(json.dumps({
            'intersection_polygon_xy_m': [[-6, -6], [6, -6], [6, 6], [-6, 6]]}))
        rows, frames = [], []
        for i in range(600):
            x = -12 if i < 100 else -11 if i < 150 else -9 if i < 250 else 0
            y = -10 if i < 50 else -4 if i < 200 else 0 if i < 300 else 10
            body = [[ox, y + oy, z] for ox in (1, 2) for oy in (-1, 1) for z in (0, 1)]
            rows.append({'native_frame': i, 'video_frame': i,
                         'source_kind': 'original_native', 'signal_id': '701',
                         'signal_state': 'inoperative_dark', 'ego_front_x_m': x + 2,
                         'ego_center_x_m': x, 'ego_speed_mps': 0 if 100 <= i < 150 else 4,
                         'other': {'speed_mps': 0 if i < 50 else 4,
                                   'body_xyz_m': body}})
            frames.append({'native_frame': i, 'video_frame': i})
        (self.root / 'native-motion.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        (self.root / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in frames))
        for name in ('capture-seal.json', 'overview.mkv', 'approach.mkv',
                     'reference_corner.mkv', 'driver_reference.mkv'):
            (self.root / name).write_text('original-shaped software test')
        self.review = {'format': 'c154537-source-context-review-v1',
                       'reviewer': 'CPU test reviewer', 'review_method': 'source-shaped test',
                       'original_sha256': {name: module.sha(self.root / name)
                                           for name in module.validate.__globals__['SOURCE_FILES']},
                       'topics': {name: {'status': 'confirmed', 'source_refs': sorted(refs),
                                         'observation': 'test observation', 'reason': 'test fixture'}
                                  for name, refs in module.REQUIRED_REFS.items()}}
        self.review_path = self.root / 'review.json'
        self.save_review()

    def save_review(self):
        self.review_path.write_text(json.dumps(self.review))

    def test_original_source_facts_keep_judgments_open(self):
        result = module.derive(self.root, self.review_path)
        self.assertEqual(result['facts']['stop_reference'], 'nearest_surveyed_view')
        self.assertTrue(result['facts']['other_stopped_before_ego'])
        self.assertFalse(result['facts']['yield_judgment_proven'])
        self.assertFalse(result['legal_verdict_claimed'])

    def test_selected_measurement_uses_separate_review(self):
        survey = json.loads((self.root / 'scene-survey.json').read_text())
        with self.assertRaisesRegex(ValueError, 'Separate original source review missing'):
            module.apply_review(self.root, survey)
        (self.root / 'source-review.json').write_text(self.review_path.read_text())
        reviewed, binding = module.apply_review(self.root, survey)
        self.assertTrue(reviewed['sidewalk_derived_crosswalk_reviewed'])
        self.assertTrue(reviewed['official_device_provenance_reviewed'])
        self.assertTrue(reviewed['through_highway_provenance_reviewed'])
        self.assertFalse(survey['sidewalk_derived_crosswalk_reviewed'])
        self.assertEqual(len(binding['confirmed_topics']), 6)
        (self.root / 'overview.mkv').write_text('mutated')
        with self.assertRaisesRegex(ValueError, 'hash differs: overview'):
            module.apply_review(self.root, survey)

    def test_changed_original_camera_rejected(self):
        (self.root / 'overview.mkv').write_text('mutated')
        with self.assertRaisesRegex(ValueError, 'hash differs: overview'):
            module.derive(self.root, self.review_path)

    def test_missing_topic_reference_rejected(self):
        self.review['topics']['through_highway']['source_refs'] = ['scene-survey.json']
        self.save_review()
        with self.assertRaisesRegex(ValueError, 'through_highway'):
            module.derive(self.root, self.review_path)

    def test_changed_governing_signal_rejected(self):
        path = self.root / 'native-motion.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[250]['signal_state'] = 'green'
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        self.review['original_sha256']['native-motion.jsonl'] = module.sha(path)
        self.save_review()
        with self.assertRaisesRegex(ValueError, 'governing signal'):
            module.derive(self.root, self.review_path)


if __name__ == '__main__':
    unittest.main()
