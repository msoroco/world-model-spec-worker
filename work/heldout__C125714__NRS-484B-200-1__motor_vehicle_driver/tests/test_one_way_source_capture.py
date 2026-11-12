import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from one_way_source_capture import OneWaySourceRecorder
from test_one_way_construction import pair


class OneWaySourceTests(unittest.TestCase):
    def test_original_actor_and_lane_readback(self):
        right,_=pair(0)
        vertices=[NS(x=i%2,y=-1+(i//2)%2,z=i//4) for i in range(8)]
        subject=NS(id=205,get_transform=lambda:object(),
                   bounding_box=NS(get_world_vertices=lambda _:vertices))
        sign=NS(id=401,type_id='static.prop.oneway',
                get_transform=lambda:NS(location=NS(x=5,y=4,z=.1)))
        with tempfile.TemporaryDirectory() as directory:
            recorder=OneWaySourceRecorder(directory,subject,sign)
            road,source=recorder.append(10,.5,right)
            self.assertEqual(road['left_lane_tangent_xy'],[1.0,0.0])
            self.assertEqual(source['actor_id'],'401')
            self.assertFalse(source['designation_verified'])
            with self.assertRaisesRegex(ValueError,'continuous'):
                recorder.append(12,.6,right)
            recorder.close()
            self.assertEqual(len((Path(directory)/'one_way_sign.jsonl').read_text().splitlines()),1)


if __name__=='__main__':
    unittest.main()
