import json
from pathlib import Path
import tempfile
import unittest

from measure_crossing import measure_crossing


class CrossingMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.geometry={'native_map_sha256':'a'*64,'approach_road_id':1,
           'straight_connector_road_id':14,'straight_destination_road_id':2,
           'right_only_lane_id':-2,'adjacent_through_lane_id':-1,
           'intersection_native_xy_bounds_m':[-7,-7,7,7],
           'right_only_lane_design_native_verified':False}
        (self.root/'road_geometry.json').write_text(json.dumps(self.geometry))

    def write(self,lane):
        y=5.25 if lane==-2 else 1.75
        states=[(-20,1),(-12,1),(0,14),(15,2)]
        records=[]
        for index,(x,road) in enumerate(states):
            body=[[x-2.6,y-1.1],[x-2.6,y+1.1],
                  [x+2.6,y+1.1],[x+2.6,y-1.1]]
            records.append({'native_frame':100+index,'time_s':.05*(index+1),
                'native_center_xy_m':[x,y],'native_forward_xy':[1,0],
                'native_body_xy_m':body,'native_road_id':road,'native_lane_id':lane})
        path=self.root/'native_samples.jsonl'
        path.write_text(''.join(json.dumps(row)+'\n' for row in records))
        return path,records

    def test_right_only_lane_crossing(self):
        path,_=self.write(-2)
        value=measure_crossing(path,self.root/'road_geometry.json')
        self.assertTrue(value['straight_through_from_right_only_lane_observed'])
        self.assertEqual(value['right_only_lane_intersection_sample_fraction'],1)
        self.assertFalse(value['right_only_lane_design_native_verified'])

    def test_adjacent_lane_straight_reference(self):
        path,_=self.write(-1)
        value=measure_crossing(path,self.root/'road_geometry.json')
        self.assertFalse(value['straight_through_from_right_only_lane_observed'])
        self.assertEqual(value['right_only_lane_intersection_sample_fraction'],0)

    def test_missing_case_source(self):
        with self.assertRaisesRegex(ValueError,'Missing required source: native_samples.jsonl'):
            measure_crossing(self.root/'native_samples.jsonl',self.root/'road_geometry.json')

    def test_lane_change_rejected(self):
        path,records=self.write(-2);records[2]['native_lane_id']=-1
        path.write_text(''.join(json.dumps(row)+'\n' for row in records))
        with self.assertRaisesRegex(ValueError,'Lane identity changed'):
            measure_crossing(path,self.root/'road_geometry.json')

    def test_incomplete_exit_rejected(self):
        path,records=self.write(-2);records[3]['native_center_xy_m']=[8,5.25]
        records[3]['native_body_xy_m']=[[5.4,4.15],[5.4,6.35],[10.6,6.35],[10.6,4.15]]
        path.write_text(''.join(json.dumps(row)+'\n' for row in records))
        with self.assertRaisesRegex(ValueError,'complete exit not all observed'):
            measure_crossing(path,self.root/'road_geometry.json')


if __name__=='__main__':unittest.main()
