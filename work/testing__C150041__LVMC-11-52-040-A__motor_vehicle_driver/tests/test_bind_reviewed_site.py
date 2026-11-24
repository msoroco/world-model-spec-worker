"""Separate synthetic packets exercise fixed-site binding, not site review."""
import copy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bind_reviewed_site import bind
from parking_site_acquisition import acquire
from test_parking_site_acquisition import NativeMap, survey


def pair(root, *, changed=None):
    paths = {}
    for activity in ('park', 'stand'):
        source = root / activity
        source.mkdir()
        survey_path, item = survey(source)
        item = copy.deepcopy(item)
        item['context']['activity'] = activity
        if activity == 'stand' and changed:
            changed(item)
        survey_path.write_text(json.dumps(item))
        native_map = NativeMap()
        native_map.name = item['native_map']['name']
        paths[activity] = acquire(native_map, survey_path, source,
                                  root / (activity + '-attempt'))
    return paths


class ReviewedSiteBindingTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / '.runtime-work' / 'c150041-binding-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_six_exact_scenes_hold_reviewed_geometry_fixed(self):
        paths = pair(self.root)
        result = bind(paths['park'], paths['stand'])
        self.assertEqual(len(result['scenes']), 6)
        self.assertEqual(result['source_kind'],
                         'separate_retained_reviewed_site_packets')
        self.assertNotEqual(result['packet_sha256']['park'],
                            result['packet_sha256']['stand'])
        self.assertTrue(all(not scene['physical_realization_claimed']
                            for scene in result['scenes'].values()))

    def test_changed_roadway_or_lawful_direction_rejected(self):
        for mutation, expected in (
            (lambda item: item['context'].update(roadway_polygon_xy_m=[[-25, 0], [25, 0], [25, 9], [-25, 9]]), 'fixed reviewed site differs'),
            (lambda item: item['native_map'].update(name='OtherMap'), 'Native map differs'),
        ):
            with self.subTest(expected=expected):
                root = self.root / str(len(list(self.root.iterdir())))
                root.mkdir()
                paths = pair(root, changed=mutation)
                with self.assertRaisesRegex(ValueError, expected):
                    bind(paths['park'], paths['stand'])

    def test_changed_retained_source_and_narrow_pose_rejected(self):
        root = self.root / 'stale'
        root.mkdir()
        paths = pair(root)
        (paths['stand'].parent / 'reviewed_sources/activity.txt').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'source hash changed'):
            bind(paths['park'], paths['stand'])
        root = self.root / 'narrow'
        root.mkdir()
        def narrow(item):
            item['context']['roadway_polygon_xy_m'] = [[-25, 0], [25, 0], [25, 3], [-25, 3]]
        paths = pair(root, changed=narrow)
        with self.assertRaisesRegex(ValueError, 'fixed reviewed site differs'):
            bind(paths['park'], paths['stand'])

    def test_changed_stand_survey_rejected(self):
        root = self.root / 'survey-stale'
        root.mkdir()
        paths = pair(root)
        (paths['stand'].parent / 'reviewed-survey.json').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'retained reviewed survey seal differs'):
            bind(paths['park'], paths['stand'])


if __name__ == '__main__':
    unittest.main()
