"""Native closure preserves original crest sources in the canonical attempt."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from canonical_crest import publish
from saved_crest_audit import ASSIGNMENT


class CanonicalCrestTests(unittest.TestCase):
    def test_original_pose_and_frames_seal_after_native_restoration(self):
        if not os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '').find('.runtime-work') >= 0:
            self.fail('runtime output root must be set under .runtime-work')
        scratch = REPO / '.runtime-work/c104084-current'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            bundle, attempt = root / 'bundle', root / 'attempt'
            bundle.mkdir()
            attempt.mkdir()
            (attempt / 'construction.json').write_text('{}\n')
            (attempt / 'runner.py').write_text('pass\n')
            case = ASSIGNMENT + '__early_decrease'
            (bundle / 'manifest.json').write_text(json.dumps({
                'case_id': case, 'native_capture_ref': 'original-capture'}) + '\n')
            motion = []
            mapping = []
            for index in range(900):
                motion.append({'frame_id': index + 10, 'time_s': index / 20,
                               'position': {'x': float(index), 'y': 0.0, 'z': 1.0},
                               'heading_deg': 0.0, 'ego_speed_mps': 10.0,
                               'ego_s_m': float(index)})
                mapping.append({'video_frame': index, 'carla_frame': index + 10,
                                'time_s': index / 20})
            (bundle / 'motion.json').write_text(json.dumps(motion) + '\n')
            (bundle / 'frame-map.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in mapping))
            for name in ('front', 'left', 'right', 'rear'):
                (bundle / (name + '.mkv')).write_bytes(name.encode())
            receipt = publish(bundle, attempt, case)
            self.assertEqual(receipt['frames'], 900)
            self.assertTrue((attempt / 'capture-seal.json').is_file())
            self.assertTrue((attempt / 'capture/crest-source/crest-manifest.json').is_file())
            self.assertEqual((attempt / 'overview.mkv').read_bytes(), b'front')
            trace = [json.loads(row) for row in (attempt / 'trace.jsonl').read_text().splitlines()]
            self.assertEqual(trace[-1]['frame'], 909)
            self.assertEqual(trace[-1]['position']['x'], 899.0)
            attempt2 = root / 'negative'
            attempt2.mkdir()
            (attempt2 / 'construction.json').write_text('{}\n')
            (attempt2 / 'runner.py').write_text('pass\n')
            motion[-1].pop('position')
            (bundle / 'motion.json').write_text(json.dumps(motion) + '\n')
            with self.assertRaisesRegex(ValueError, 'pose/frame identity'):
                publish(bundle, attempt2, case)
            self.assertFalse((attempt2 / 'capture-seal.json').exists())


if __name__ == '__main__':
    unittest.main()
