"""Check official-vehicle identity and the measured response separately."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'native'))
from measure_official import measure


class OfficialMeasurement(unittest.TestCase):
    def test_source_bound_official_approach(self):
        result = measure(HERE / 'current-fixture/official_approach')
        self.assertEqual(result['samples'], 600)
        self.assertTrue(result['right_edge_stop_until_passed_observed'])
        self.assertEqual(result['emergency_pass_frame'], 580)
        self.assertIsNone(result['legal_result'])

    def test_missing_agency_review_is_rejected(self):
        source = HERE / 'current-fixture/official_approach'
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work/c405647-267-2f/tmp') as temporary:
            target = Path(temporary)
            for name in ('video_frames.jsonl', 'vehicle_poses.jsonl', 'emergency_context.json'):
                (target / name).write_bytes((source / name).read_bytes())
            context = json.loads((target / 'emergency_context.json').read_text())
            context['official_vehicle_reviewed'] = False
            (target / 'emergency_context.json').write_text(json.dumps(context) + '\n')
            with self.assertRaisesRegex(ValueError, 'official identity'):
                measure(target)


if __name__ == '__main__':
    unittest.main()
