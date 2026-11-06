import json
from pathlib import Path
import tempfile
import unittest

from measure_purpose import measure_lane_use


class LanePurposeMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.geometry={'native_map_sha256':'a'*64,'approach_road_id':1,
                       'right_only_lane_id':-2,'right_turn_connector_road_id':13,
                       'straight_connector_road_id':14,'right_turn_destination_road_id':4,
                       'straight_destination_road_id':2,
                       'right_only_lane_design_native_verified':False}
        (self.root/'road_geometry.json').write_text(json.dumps(self.geometry))

    def write(self,movement):
        states=[(-20,5.25,(1,0),1,-2),(-12,5.25,(1,0),1,-2)]
        if movement=='turn':states += [(-3,5.25,(.7,.714142842),13,-2),(-5.25,12,(0,1),4,-2)]
        else:states += [(0,5.25,(1,0),14,-2),(15,5.25,(1,0),2,-2)]
        samples=[]
        for i,(x,y,forward,road,lane) in enumerate(states):
            half_x,half_y=(2.6,1.1) if road in (1,2,14) else (1.1,2.6)
            body=[[x-half_x,y-half_y],[x-half_x,y+half_y],
                  [x+half_x,y+half_y],[x+half_x,y-half_y]]
            samples.append({'native_frame':100+i,'time_s':.05*(i+1),
                'native_center_xy_m':[x,y],'native_forward_xy':list(forward),
                'native_body_xy_m':body,'native_road_id':road,'native_lane_id':lane})
        path=self.root/'native_samples.jsonl'
        path.write_text(''.join(json.dumps(row)+'\n' for row in samples))
        return path,samples

    def test_right_turn_after_lane_use(self):
        path,_=self.write('turn')
        result=measure_lane_use(path,self.root/'road_geometry.json')
        self.assertEqual(result['observed_subsequent_movement'],'right_turn_follows')
        self.assertEqual(result['right_only_lane_identity_fraction'],1)
        self.assertTrue(result['full_body_in_right_only_lane_approach_samples'])
        self.assertFalse(result['right_only_lane_design_native_verified'])

    def test_straight_after_lane_use(self):
        path,_=self.write('straight')
        self.assertEqual(measure_lane_use(path,self.root/'road_geometry.json')['observed_subsequent_movement'],'straight_follows')

    def test_missing_case_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'Missing required source: native_samples.jsonl'):
            measure_lane_use(self.root/'native_samples.jsonl',self.root/'road_geometry.json')

    def test_connector_disagreement_rejected(self):
        path,rows=self.write('turn');rows[2]['native_road_id']=14
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with self.assertRaisesRegex(ValueError,'Connector and completed movement disagree'):
            measure_lane_use(path,self.root/'road_geometry.json')

    def test_missing_exit_rejected(self):
        path,rows=self.write('straight');rows.pop()
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with self.assertRaisesRegex(ValueError,'Too few Native samples'):
            measure_lane_use(path,self.root/'road_geometry.json')


if __name__=='__main__':unittest.main()
