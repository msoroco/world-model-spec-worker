import queue
import unittest
from types import SimpleNamespace

import analyze
import runner
from scenario import route,static_check


class SignalTests(unittest.TestCase):
    def test_geometry_and_case(self):
        runner.check()
        self.assertGreater(static_check()['route_points'],190)
        self.assertLess(route(None)[-1][1],-60)

    def test_course_onset_uses_sustained_heading(self):
        rows=[{'heading_deg':0} for _ in range(7)]+[{'heading_deg':4} for _ in range(3)]
        self.assertEqual(7,analyze.course_onset(rows))

    def test_camera_warmup(self):
        q=queue.Queue()
        for n in (2,3,4):q.put(SimpleNamespace(frame=n))
        self.assertEqual(4,runner.image_for_frame(q,4).frame)


if __name__=='__main__':unittest.main()


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
