"""Exercise the independent comparison's positive and rejection branches."""
import json
import tempfile
import unittest
from pathlib import Path

from comparison_audit import AID, SOURCES, audit, sha


class ComparisonAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dirs, self.observations = [], []
        for index, (speed, count) in enumerate(((78.0, 0), (80.0, 0), (82.0, 600)), 1):
            source = Path(self.tmp.name)/f'probe_{index:02d}'
            source.mkdir()
            context = {'assignment_id': AID, 'case_id': AID+f'__probe_{index:02d}',
                       'route_source': 'reviewed route A', 'vehicle_identity_source': 'same blueprint',
                       'other_vehicle_source': 'separate original actor',
                       'driving_state_source': 'Native control'}
            context_path = source/'road_context.json'
            context_path.write_text(json.dumps(context)+'\n')
            for name in SOURCES-{'road_context.json'}:
                (source/name).write_text('synthetic source shape\n')
            observation = {'format': 'saved-absolute-speed-observation', 'assignment_id': AID,
                           'review_kind': 'original_source_review', 'sources': {name: sha(source/name) for name in SOURCES},
                           'statutory_cap_mph': 80.0, 'sample_count': 600, 'driving_frame_count': 600,
                           'maximum_observed_mph_while_driving': speed,
                           'frames_above_80_mph': list(range(count)),
                           'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
            observation_path = source/'observation.json'
            observation_path.write_text(json.dumps(observation)+'\n')
            self.dirs.append(source)
            self.observations.append(observation_path)

    def test_positive(self):
        result = audit(self.dirs, self.observations)
        self.assertEqual(len(result['cases']), 3)

    def test_rejects_stale_context(self):
        path = self.dirs[0]/'road_context.json'
        path.write_text(path.read_text().replace('reviewed route A', 'different route'))
        with self.assertRaisesRegex(ValueError, 'context hash stale'):
            audit(self.dirs, self.observations)

    def test_rejects_changed_fixed_condition(self):
        path = self.dirs[0]/'road_context.json'
        context = json.loads(path.read_text())
        context['route_source'] = 'different route'
        path.write_text(json.dumps(context)+'\n')
        observation_path = self.observations[0]
        observation = json.loads(observation_path.read_text())
        observation['sources']['road_context.json'] = sha(path)
        observation_path.write_text(json.dumps(observation)+'\n')
        with self.assertRaisesRegex(ValueError, 'fixed route'):
            audit(self.dirs, self.observations)

    def test_rejects_missing_boundary(self):
        path = self.observations[1]
        observation = json.loads(path.read_text())
        observation['maximum_observed_mph_while_driving'] = 79.5
        path.write_text(json.dumps(observation)+'\n')
        with self.assertRaisesRegex(ValueError, 'boundary not established'):
            audit(self.dirs, self.observations)

    def test_rejects_missing_saved_source(self):
        (self.dirs[2]/'native_motion.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'source hash stale'):
            audit(self.dirs, self.observations)


if __name__ == '__main__':
    unittest.main()
