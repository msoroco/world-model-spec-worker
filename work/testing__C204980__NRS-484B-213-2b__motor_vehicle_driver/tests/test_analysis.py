import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
from analysis import analyze
from test_rail_capture import FakeAdapter
from test_reviewed_rail import AID, make
from rail_capture import capture
from rail_left import CASES


CHANNELS = ('rail_qualification', 'highway_direction', 'crossing_extent',
            'ego_body_side_and_station', 'original_frame_and_camera_join')


def fixture(root, suffix='left_99ft'):
    packet, map_text, case_id = make(root, suffix)
    case = next(c for c in CASES if c.case_id == suffix)
    attempt = root / 'attempt'; attempt.mkdir()
    capture(FakeAdapter(map_text, case), packet, root, attempt, case_id)
    config = {'assignment_id': AID, 'selected_case_id': case_id,
              'duration_s': 45, 'rate_hz': 20,
              'case': {'recording_description': {'channels': [
                  {'name': name, 'unit': 'structured record'} for name in CHANNELS],
                  'context_inputs': []}}}
    (attempt / 'config.json').write_text(json.dumps(config))
    return attempt, case_id


class SavedAnalysisTests(unittest.TestCase):
    def test_all_six_saved_cases_and_measurement_source_hashes(self):
        for suffix in (c.case_id for c in CASES):
            with tempfile.TemporaryDirectory() as folder:
                attempt, case_id = fixture(Path(folder), suffix)
                source_before = (attempt / 'source-hashes.json').read_bytes()
                report = analyze(attempt, assignment_id=AID, case_id=case_id)
                self.assertEqual(set(report['measurements']), {
                    'left_side_measurement', 'crossing_distance_measurement',
                    'traversal_measurement', 'rail_qualification_measurement',
                    'one_way_measurement'})
                self.assertFalse(report['legal_verdict_claimed'])
                self.assertEqual((attempt / 'source-hashes.json').read_bytes(), source_before)
                self.assertEqual(len((attempt / 'video_frames.jsonl').read_text().splitlines()), 900)
                self.assertEqual(len((attempt / 'result.json').read_text().splitlines()), 1)

    def test_rejects_missing_original_railroad_source(self):
        with tempfile.TemporaryDirectory() as folder:
            attempt, case_id = fixture(Path(folder))
            (attempt / 'reviewed-railroad.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: reviewed-railroad.json'):
                analyze(attempt, assignment_id=AID, case_id=case_id)
            self.assertFalse((attempt / 'result.json').exists())


if __name__ == '__main__':
    unittest.main()
