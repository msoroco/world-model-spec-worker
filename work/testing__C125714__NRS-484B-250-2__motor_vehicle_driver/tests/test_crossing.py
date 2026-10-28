import unittest
import xml.etree.ElementTree as ET
import queue
from types import SimpleNamespace

import analyze
import runner
import scenario


class CrossingTests(unittest.TestCase):
    def test_exact_southern_crossing_has_no_device(self):
        runner.check()
        root = ET.fromstring(scenario.build_xodr())
        junctions = {j.attrib['id']: j for j in root.findall('junction')}
        self.assertEqual({1, 5}, {int(c.attrib['incomingRoad']) for c in junctions['10']})
        self.assertFalse(root.findall('.//signals/signal'))

    def test_entry_bracket_keeps_sampling_uncertainty(self):
        rows = [{'time_s': .05, 'ego': {'inside_crossing': False}},
                {'time_s': .10, 'ego': {'inside_crossing': True}}]
        self.assertEqual([.05, .10], analyze.bracket(rows, 'ego'))

    def test_camera_warmup_frames_are_discarded(self):
        q = queue.Queue()
        for frame in (3, 4, 5, 6):
            q.put(SimpleNamespace(frame=frame))
        self.assertEqual(5, runner.image_for_frame(q, 5).frame)
        with self.assertRaisesRegex(RuntimeError, 'frame mismatch'):
            runner.image_for_frame(q, 5)


if __name__ == '__main__':
    unittest.main()


class OriginalSourceAuditTests(unittest.TestCase):
    def test_missing_frame_map_is_rejected_before_video_decode(self):
        import tempfile
        from pathlib import Path
        from source_audit import audit_sources
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'video_frames.jsonl').write_text('')
            (root/'trace.jsonl').write_text('')
            (root/'capture').mkdir()
            (root/'capture/evidence.jsonl').write_text('')
            with self.assertRaisesRegex(ValueError,'counts differ'):
                audit_sources(root,{'case':{'recording_description':{'channels':[]}},'cameras':[]},
                              [{'frame':1,'time_s':0.05}])
