import queue
import unittest
from types import SimpleNamespace

import runner
from scenario import build_xodr, static_check


class OneWayTests(unittest.TestCase):
    def test_geometry_and_case_route(self):
        runner.check()
        self.assertEqual(2, static_check()['eastbound_driving_lanes'])
        self.assertIn('OneWay', build_xodr())

    def test_old_camera_frames_dropped(self):
        q = queue.Queue()
        for frame in (3, 4, 5):
            q.put(SimpleNamespace(frame=frame))
        self.assertEqual(5, runner.image_for_frame(q, 5).frame)


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
