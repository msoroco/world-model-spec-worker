import json
from pathlib import Path
import tempfile
import unittest
from measure_exit import measure


def row(t,x,y,forward=(1,0)):
    return {'time_s':t,'native_forward_xy':list(forward),
            'native_body_xy_m':[[x-1.1,y-2.6],[x+1.1,y-2.6],
                                [x+1.1,y+2.6],[x-1.1,y+2.6]]}


class ExitMeasurementTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.geometry=self.root/'road_geometry.json'
        self.samples=self.root/'native_samples.jsonl'
        self.geometry.write_text(json.dumps({'native_map_sha256':'a'*64,
          'road_directions_native':{'approach_forward':[1,0],
            'approach_opposing':[-1,0],'destination_forward':[0,-1],
            'destination_opposing':[0,1]},
          'destination_right_normal_native':[1,0],
          'destination_centerline_point_native_m':[0,0],
          'destination_exit_point_native_m':[0,-7]}))

    def write(self,x):
        self.samples.write_text('\n'.join(json.dumps(r) for r in
          [row(.05,-20,1.75),row(.10,x,-5,(0,-1)),row(.15,x,-11,(0,-1))])+'\n')

    def test_distinct_full_body_exit_sides(self):
        for x,expected in ((1.75,'right'),(-1.75,'left')):
            with self.subTest(x=x):
                self.write(x);result=measure(self.samples,self.geometry)
                self.assertEqual(result['geometric_side'],expected)
                self.assertEqual(result['first_full_body_exit_time_bracket_s'],[.1,.15])

    def test_missing_opposing_direction_rejected(self):
        self.write(1.75)
        data=json.loads(self.geometry.read_text())
        data['road_directions_native']['destination_opposing']=[0,-1]
        self.geometry.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'Two-way Native direction evidence missing'):
            measure(self.samples,self.geometry)

    def test_reversed_destination_right_axis_rejected(self):
        self.write(1.75)
        data=json.loads(self.geometry.read_text())
        data['destination_right_normal_native']=[-1,0]
        self.geometry.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'Destination right axis differs'):
            measure(self.samples,self.geometry)

    def test_incomplete_turn_rejected(self):
        self.write(1.75)
        data=[json.loads(s) for s in self.samples.read_text().splitlines()]
        data[-1]['native_forward_xy']=[1,0]
        self.samples.write_text('\n'.join(json.dumps(r) for r in data)+'\n')
        with self.assertRaisesRegex(ValueError,'No full-body destination exit'):
            measure(self.samples,self.geometry)


if __name__=='__main__':unittest.main()
