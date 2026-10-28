import queue
import unittest
from types import SimpleNamespace

import runner
from scenario import route, static_check


class SpeedTests(unittest.TestCase):
    def test_paved_two_lane_geometry_and_route(self):
        runner.check()
        self.assertEqual(2, static_check()['same_direction_lanes'])
        self.assertEqual(3.5, abs(route('ego')[0][1]-route('traffic')[0][1]))

    def test_camera_warmup_discard(self):
        q=queue.Queue()
        for frame in (2,3,4):q.put(SimpleNamespace(frame=frame))
        self.assertEqual(4,runner.image_for_frame(q,4).frame)


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
