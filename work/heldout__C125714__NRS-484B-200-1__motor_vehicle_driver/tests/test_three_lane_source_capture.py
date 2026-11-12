import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from three_lane_source_capture import ThreeLaneSourceRecorder
from test_three_lane_construction import section


class ThreeLaneSourceTests(unittest.TestCase):
    def test_original_lane_and_body_readback(self):
        right,_,_=section(0)
        vertices=[NS(x=i%2,y=(i//2)%2,z=i//4) for i in range(8)]
        ego=NS(id=205,get_transform=lambda:object(),
               bounding_box=NS(get_world_vertices=lambda _:vertices))
        with tempfile.TemporaryDirectory() as directory:
            recorder=ThreeLaneSourceRecorder(directory,ego)
            row=recorder.append(10,.5,right)
            self.assertEqual(row['lane_widths_m'],[3.5,3.5,3.5])
            self.assertEqual(row['ego_id'],'205')
            with self.assertRaisesRegex(ValueError,'continuous'):
                recorder.append(12,.6,right)
            recorder.close()


if __name__=='__main__':
    unittest.main()
