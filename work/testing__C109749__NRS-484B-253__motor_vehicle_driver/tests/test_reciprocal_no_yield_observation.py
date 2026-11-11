import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent.parent
SOURCE = REPO / '.runtime-work/c109749-seven-case-reciprocal_continues_after_turn-primary-compat-v1'
sys.path.insert(0, str(ROOT))
from reciprocal_no_yield_observation import observe


class ReciprocalNoYieldObservationTests(unittest.TestCase):
    def fixture(self, root, mutate=None):
        for name in ('intersection_geometry.json', 'interaction_history.jsonl', 'video_frames.jsonl'):
            shutil.copyfile(SOURCE / name, root / name)
        if mutate:
            rows = [json.loads(line) for line in (root/'interaction_history.jsonl').read_text().splitlines() if line.strip()]
            mutate(rows)
            (root/'interaction_history.jsonl').write_text('\n'.join(map(json.dumps, rows))+'\n')

    @staticmethod
    def enter_during_turn(rows):
        for index, x in ((5, 12), (6, 5), (7, 2), (8, -1)):
            actor = rows[index]['reciprocal']
            actor['position_xy_m'] = [x, 0]
            actor['body_vertices_xy_m'] = [[x-1,-1],[x+1,-1],[x+1,1],[x-1,1]]
            actor['velocity_xy_mps'] = [-6, 0]

    def test_continuing_approach_without_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'did not enter'):
                observe(root)

    def test_distinct_entry_during_turn_is_measured(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, self.enter_during_turn)
            result = observe(root)
            self.assertLess(result['ego_turn_start_frame'], result['later_opposing_entry_frame'])
            self.assertLess(result['later_opposing_entry_frame'], result['ego_exit_frame'])
            self.assertFalse(result['legal_verdict_asserted'])

    def test_stopped_actor_and_missing_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def stopped(rows):
                self.enter_during_turn(rows)
                rows[6]['reciprocal']['velocity_xy_mps'] = [0, 0]
            self.fixture(root, stopped)
            with self.assertRaisesRegex(ValueError, 'stopped'):
                observe(root)
            (root/'video_frames.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                observe(root)


if __name__ == '__main__':
    unittest.main()
