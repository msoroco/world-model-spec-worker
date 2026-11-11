import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from native_headlamp_probe import seal_provenance


class NativeSealTests(unittest.TestCase):
    def test_complete_closed_capture_seals_original_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('construction.json', 'runner.py', 'trace.jsonl', 'video_frames.jsonl'):
                (root / name).write_text('original\n')
            route = {'ego': SimpleNamespace(road_id=4, lane_id=1), 'requested_gap_ft': 299}
            with self.assertRaisesRegex(ValueError, 'complete frame sequence'):
                seal_provenance(root, [], route, 'Town04')
            seal = seal_provenance(root, [10, 11], route, 'Town04')
            self.assertEqual(seal['events'], ['capture_finished', 'encoders_closed',
                                              'restoration_verified'])
            self.assertEqual(seal['frames'], 2)
            self.assertFalse(seal['physical_acceptance_claimed'])
            self.assertFalse(json.loads((root / 'acquisition-provenance.json').read_text())
                             ['diagnostic_fixture'])


if __name__ == '__main__':
    unittest.main()
