import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ending_road_official_finalizer import measure_official_device


class OfficialDeviceFinalizerTests(unittest.TestCase):
    def test_original_governing_link_and_stale_state_rejection(self):
        files = json.loads((ROOT / 'diagnostic-official-device.json').read_text())['files']
        names = ('official_device_context.json', 'official_device_states.jsonl',
                 'intersection_topology.json', 'video_frames.jsonl')
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for name in names:
                path = Path(directory) / name
                path.write_text(files[name])
                paths.append(path)
            observed = measure_official_device(*paths)
            self.assertEqual(observed['frames'], 9)
            self.assertFalse(observed['official_legal_status_claimed'])
            context = json.loads(paths[0].read_text())
            context['affected_lane_id'] = -2
            paths[0].write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, 'does not govern'):
                measure_official_device(*paths)
            paths[0].write_text(files[names[0]])
            rows = [json.loads(line) for line in paths[1].read_text().splitlines()]
            rows[1]['frame'] += 1
            paths[1].write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'state join failed'):
                measure_official_device(*paths)
