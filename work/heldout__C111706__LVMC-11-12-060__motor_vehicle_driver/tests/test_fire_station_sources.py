import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as S


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fire_station_sources import StationSourceRecorder
from fire_station_measurement import measure


class Actor:
    def __init__(self, identity, x, y, yaw):
        self.id, self.x, self.y, self.yaw = identity, x, y, yaw
        self.bounding_box = self

    def get_transform(self):
        return S(location=S(x=self.x,y=self.y),rotation=S(yaw=self.yaw))

    def get_world_vertices(self, transform):
        return [S(x=self.x+dx,y=self.y+dy,z=z)
                for z in (0,2) for dx,dy in ((-1,-.4),(1,-.4),(1,.4),(-1,.4))]


class Map:
    def get_waypoint(self, location):
        return S(road_id=8 if location.y > 1 else 7,
                 lane_id=2 if location.y > 1 else (1 if location.y < 1 else -1))


def survey(reverse=False):
    def wp(x,y,road=7,lane=1):
        return {'xy':[x,y],'road_id':road,'lane_id':lane,'lane_width':3.0}
    return {'station_source':{'kind':'operator_survey','asset_id':'source-backed-test-station',
                              'source_sha256':'2'*64},
            'public_before':wp(8 if reverse else -8,0),
            'public_at':wp(0,0),
            'public_after':wp(-8 if reverse else 8,0),
            'driveway_at':wp(0,6,8,2)}


class StationSourceTests(unittest.TestCase):
    def test_both_directions_retain_original_bodies_for_saved_measurement(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                recorder = StationSourceRecorder(root, survey(reverse))
                ego = Actor(1, 5 if reverse else -5, 0, 180 if reverse else 0)
                other = Actor(2, 12, 0, 180)
                mapping, trace = [], []
                for index, (x,y,yaw) in enumerate((
                        (5,0,180),(0,3,270),(5,0,360)) if reverse else
                        ((-5,0,0),(0,3,90),(-5,0,180))):
                    ego.x,ego.y,ego.yaw=x,y,yaw
                    recorder.append(10+index,index*.05,ego,other,Map())
                    mapping.append({'video_frame':index,'carla_frame':10+index,
                                    'time_s':index*.05})
                    trace.append({'frame':10+index,'time_s':index*.05})
                recorder.close()
                for name,rows in (('video_frames.jsonl',mapping),('trace.jsonl',trace)):
                    (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
                observed = measure(root)
                self.assertTrue(observed['path']['entered_driveway'])
                self.assertTrue(observed['path']['reversal_observed'])
                self.assertEqual((observed['subject_actor_id'],observed['other_actor_id']), (1,2))

    def test_rejects_reused_sources_and_nonmonotonic_native_tick(self):
        with tempfile.TemporaryDirectory() as temp:
            recorder = StationSourceRecorder(temp, survey())
            ego, other = Actor(1,-5,0,0), Actor(2,12,0,180)
            recorder.append(10,0,ego,other,Map())
            with self.assertRaisesRegex(ValueError,'consecutive 20 Hz'):
                recorder.append(12,.05,ego,other,Map())
            recorder.close()
            with self.assertRaises(FileExistsError):
                StationSourceRecorder(temp,survey())


if __name__ == '__main__':
    unittest.main()
