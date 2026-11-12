import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from one_way_measurement import measure_one_way


class OneWayMeasurementTests(unittest.TestCase):
    def test_original_sign_lane_and_frame_source_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            road=[];sign=[];frames=[];trace=[]
            for i in range(4):
                road.append({'frame':i,'time_s':i*.05,'ego_id':'205',
                    'travel_tangent_xy':[1,0],'left_lane_tangent_xy':[1,0],
                    'roadway_center_point_xy':[0,0],
                    'left_road_edge_xy':[0,-3.5],'right_road_edge_xy':[0,3.5],
                    'ego_corners':[[i,-2],[i,-1],[i+1,-2],[i+1,-1]]})
                sign.append({'frame':i,'time_s':i*.05,'actor_id':'sign-1',
                    'blueprint_id':'static.prop.one_way','position_m':[5,4,0],
                    'designation_verified':False,'posting_authority_verified':False})
                frames.append({'video_frame':i,'carla_frame':i,'time_s':i*.05})
                trace.append({'frame':i,'time_s':i*.05})
            def write():
                for name,rows in [('one_way_roadway.jsonl',road),('one_way_sign.jsonl',sign),
                                  ('video_frames.jsonl',frames),('trace.jsonl',trace)]:
                    (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
            write()
            self.assertEqual(measure_one_way(root)['sign_actor_id'],'sign-1')
            sign[0]['posting_authority_verified']=True;write()
            with self.assertRaisesRegex(ValueError,'unsupported authority'):
                measure_one_way(root)
            sign[0]['posting_authority_verified']=False
            road[1]['left_lane_tangent_xy']=[-1,0];write()
            with self.assertRaisesRegex(ValueError,'same-direction'):
                measure_one_way(root)
            (root/'one_way_sign.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                measure_one_way(root)


if __name__=='__main__':
    unittest.main()
