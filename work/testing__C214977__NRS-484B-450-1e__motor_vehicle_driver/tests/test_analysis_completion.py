import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import assess_crosswalk_halt


class CompletionTests(unittest.TestCase):
    def test_driven_halt_and_wrong_destination(self):
        context = {'action': 'park', 'destination': 'on',
                   'crosswalk_polygon': [[0, 0], [4, 0], [4, 4], [0, 4]]}
        rows = []
        for i in range(900):
            x = -5 + 7 * min(i / 800, 1)
            rows.append({'frame': 100+i, 'time_s': i*.05,
                         'body_corners_xy': [[x-1, 1], [x+1, 1], [x+1, 3], [x-1, 3]],
                         'speed_mps': 0 if i >= 800 else 1,
                         'halt_activity': 'park' if i >= 800 else 'travel'})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('crosswalk-context.json', 'crosswalk-rows.jsonl',
                         'trace.jsonl', 'video_frames.jsonl'):
                (root/name).write_text(json.dumps(context if name.endswith('.json') else rows)+'\n')
            good = assess_crosswalk_halt(root, context, rows, 'met')
            self.assertEqual(good['status'], 'met')
            self.assertGreater(good['details']['sampled_path_m'], 1)
            self.assertEqual(good['details']['terminal_halt_frames'], 100)
            wrong = dict(context, destination='off')
            self.assertEqual(assess_crosswalk_halt(root, wrong, rows, 'met')['status'], 'not_met')
            self.assertEqual(assess_crosswalk_halt(root, context, rows, 'not_met')['status'], 'not_met')


if __name__ == '__main__':
    unittest.main()
