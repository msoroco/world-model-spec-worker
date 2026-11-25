import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('reference_fixture_builder',
                                              ROOT / 'build_reference_fixture.py')
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class ReferenceFixtureBuilderTests(unittest.TestCase):
    def test_three_reference_fixtures_bind_600_frames_under_return_cap(self):
        for suffix in ('stop_line_reference', 'crosswalk_reference',
                       'nearest_view_reference'):
            with self.subTest(suffix=suffix):
                source, recipe_path = BUILDER.build(suffix)
                spec = json.loads(source.read_text())
                recipe = json.loads(recipe_path.read_text())
                self.assertLessEqual(source.stat().st_size, 2 * 1024 * 1024)
                self.assertEqual(recipe['generator']['sha256'],
                                 hashlib.sha256(source.read_bytes()).hexdigest())
                capture = json.loads(spec['files']['officer-reference-capture.json'])
                self.assertEqual(len(capture['rows']), 600)
                self.assertEqual(len(spec['graphs']), 1200)
                self.assertEqual({v['frames'] for v in spec['videos']}, {600})
                self.assertEqual(capture['case_id'], BUILDER.PREFIX + suffix)


if __name__ == '__main__':
    unittest.main()
