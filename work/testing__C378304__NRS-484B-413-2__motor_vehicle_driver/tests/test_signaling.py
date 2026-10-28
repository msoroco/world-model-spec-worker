import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import signaling
class Signals(unittest.TestCase):
 def test_observed_distance_and_interruption(self):
  rows=[{'position':[i*2,0,0],'time_s':i/20,'right_indicator':i!=2} for i in range(7)]
  result=signaling.continuous_signal_distance(rows,6)
  self.assertEqual(result['value_m'],6);self.assertEqual(result['sample_window_s'],[.15,.3]);self.assertIsNone(result['indicator_optically_confirmed'])
 def test_optical_raw_evidence_not_verdict(self):
  self.assertEqual(signaling.mean_roi_luminance_bgra(bytes([0,0,255,255]),1,1,[0,0,1,1]),.2126*255)
  self.assertIsNone(signaling.optical_variation([{'time_s':0,'roi_luminance':20},{'time_s':1,'roi_luminance':100}])['confirmed'])
 def test_empty_and_bad_evidence(self):
  self.assertFalse(signaling.optical_variation([])['confirmed'])
  with self.assertRaises(ValueError):signaling.continuous_signal_distance([],0)
