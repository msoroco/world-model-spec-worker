import unittest,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from worker_exchange.optical_measurements import photometry,project_body
class Optical(unittest.TestCase):
 def test_raw_rgb_is_measured(self):
  r=photometry(bytes([0,0,255,255])*4,2,2,[0,0,2,2]);self.assertAlmostEqual(r['mean_luminance'],.2126*255);self.assertEqual(r['pixel_count'],4)
 def test_bad_frame_fails(self):self.assertRaises(ValueError,photometry,b'bad',2,2,[0,0,2,2])
 def test_invalid_crop_fails(self):self.assertRaises(ValueError,photometry,bytes(16),2,2,[0,0,3,3])
 def test_body_projection(self):
  identity=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]];self.assertEqual(project_body([[10,-1,-1],[10,1,1]],identity,100,100,90),[45,45,55,55])
 def test_behind_camera_fails(self):self.assertRaises(ValueError,project_body,[[-1,0,0]],[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],100,100,90)
