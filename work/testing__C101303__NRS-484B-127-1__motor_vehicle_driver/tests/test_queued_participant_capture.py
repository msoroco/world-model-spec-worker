import io
import json
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from test_capture_sources import FakeActor

FOLDER = Path(__file__).resolve().parents[1]
CONSTRUCTION = FOLDER/'cases/source_verified_queued_traffic/construction.json'


class QueuedParticipantCaptureTest(unittest.TestCase):
    def test_retains_queued_body_and_rejects_unrecorded_actor(self):
        construction = json.loads(CONSTRUCTION.read_text())
        source = next(f['content'] for f in construction['files'] if f['path']=='capture_sources.py')
        module = types.ModuleType('queued_capture_sources')
        exec(compile(source, str(CONSTRUCTION), 'exec'), module.__dict__)
        ego, lead, queued = FakeActor(11, 0, 5), FakeActor(22, 10, 4), FakeActor(33, 28, 0)
        snapshot = NS(frame=100, timestamp=NS(elapsed_seconds=1.0))
        calls = []
        frame_map = NS(append=lambda frame, time: calls.append((frame,time)) or {'video_frame':0})
        stream = io.StringIO()
        kwargs = dict(road_id=7,ego_lane_id=-1,lead_lane_id=-1,surface_condition='dry',
                      traffic_actor_ids=[11,22,33],lane_change_started=False,
                      additional_actors=[(queued,-1)])
        result = module.record_sample(frame_map,stream,snapshot,ego,lead,**kwargs)
        self.assertEqual(result['history']['other_participants'][0]['actor_id'],33)
        self.assertEqual(len(result['history']['other_participants'][0]['body_vertices_xy_m']),4)
        self.assertEqual(result['history']['other_participants'][0]['velocity_mps'],[0.,0.,0.])
        self.assertEqual(calls,[(100,1.0)])
        with self.assertRaisesRegex(ValueError,'Traffic inventory lacks complete participant state'):
            module.record_sample(frame_map,io.StringIO(),snapshot,ego,lead,**{**kwargs,'additional_actors':[]})
        self.assertEqual(calls,[(100,1.0)])


if __name__ == '__main__':
    unittest.main()
