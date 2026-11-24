import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from canonical_bridge import bridge


class CanonicalBridgeTests(unittest.TestCase):
    def test_rejects_missing_owner_graph_before_seal(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temp:
            root = Path(temp)
            original = root / 'original-attempt'
            original.mkdir()
            (root / 'construction.json').write_text('{}\n')
            (root / 'runner.py').write_text('# original runner\n')
            ego = [{'frame': 100 + i, 'time_s': i / 20,
                    'x': float(i), 'y': 0.0, 'speed_mps': 1.0,
                    'yaw_rad': 0.0, 'velocity_mps': [1, 0, 0]}
                   for i in range(20)]
            (original / 'trace.json').write_text(json.dumps({'ego': ego}) + '\n')
            rows = [{'frame': item['frame'], 'time_s': item['time_s'],
                     'cameras': {}} for item in ego]
            (original / 'frame-map.jsonl').write_text(''.join(
                json.dumps(row) + '\n' for row in rows))
            for name in ('map-packet.json', 'authority.json', 'road.xodr'):
                (original / name).write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'original camera archive missing'):
                bridge(root, original, release={
                    'world_restored': True, 'actors_released': True,
                    'sensors_released': True, 'readback_passed': True},
                    expected_frames=20)
            self.assertFalse((root / 'capture-seal.json').exists())


if __name__ == '__main__':
    unittest.main()
