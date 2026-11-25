"""Source-bound positive and damaged-source negatives for selected lane semantics."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('selected_lane', HERE / 'audit-selected-semantic.py')
LANE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LANE)
FILES = ('scene.xodr', 'road_geometry.json', 'native_samples.jsonl', 'video_frames.jsonl')


class SourceSemanticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        source = HERE / 'selected-v2-source/controlled_1'
        for name in FILES:
            shutil.copyfile(source / name, self.folder / name)

    def test_positive(self):
        report = LANE.audit(self.folder)
        self.assertTrue(report['passed'])
        self.assertFalse(report['core_center_lane_projection_claimed'])

    def test_changed_map(self):
        path = self.folder / 'scene.xodr'
        path.write_text(path.read_text().replace('left_turn_only_both_directions', 'general_use', 1))
        with self.assertRaises(ValueError):
            LANE.audit(self.folder)

    def test_changed_native_lane(self):
        path = self.folder / 'native_samples.jsonl'
        data = [json.loads(line) for line in path.read_text().splitlines()]
        for row in data:
            row['native_lane_id'] = -2
        path.write_text(''.join(json.dumps(row) + '\n' for row in data))
        with self.assertRaisesRegex(ValueError, 'No source-bound'):
            LANE.audit(self.folder)

    def test_missing_body(self):
        path = self.folder / 'native_samples.jsonl'
        data = [json.loads(line) for line in path.read_text().splitlines()]
        for row in data:
            row['native_body_xy_m'] = []
        path.write_text(''.join(json.dumps(row) + '\n' for row in data))
        with self.assertRaisesRegex(ValueError, 'No source-bound'):
            LANE.audit(self.folder)


if __name__ == '__main__':
    unittest.main()
