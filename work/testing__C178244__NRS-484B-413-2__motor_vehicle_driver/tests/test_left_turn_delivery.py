import json
import math
import unittest
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("left_turn_delivery", Path(__file__).resolve().parents[1]/"left_turn_delivery.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TestLeftTurnPrimary(unittest.TestCase):
    def test_exact_map_source(self):
        import hashlib
        self.assertEqual(hashlib.sha256(m.build_left_turn_opendrive().encode()).hexdigest(), m.MAP_SHA256)
        text = m.build_left_turn_opendrive()
        self.assertIn('curvature="0.1"', text)
        self.assertIn('northbound departure', text)
    def test_exact_capture_contract(self):
        cfg = json.loads((Path(__file__).resolve().parents[1]/"config.json").read_text())
        self.assertEqual(m.validate_capture_config(cfg)["physical_completion"]["destination_road"],178247)
        self.assertEqual(set(m.CAMERAS),{"overview","approach","reference_corner","driver_reference"})
    def test_left_signal_schedule(self):
        self.assertFalse(m.indicator_request_at_remaining_distance(31.0,start_m=30.98))
        self.assertTrue(m.indicator_request_at_remaining_distance(30.0,start_m=30.98))
        self.assertFalse(m.indicator_request_at_remaining_distance(20.0,start_m=30.98,interruption_m=(19,21)))
    def test_route_direction(self):
        class P:
            def __init__(self,road,s,x,y):
                self.road_id=road;self.lane_id=-1;self.s=s
                self.transform=type('T',(),{'location':type('L',(),{'x':x,'y':y})()})()
        approach=[P(178244,i*2,-120+i*2,-1.8) for i in range(61)]
        departure=[P(178246,i*2,2*math.sin(i*.2),-1.8+2*(1-math.cos(i*.2))) for i in range(9)]
        self.assertGreater(m.verify_native_left_turn(approach,departure)['turn_angle_deg'],30)
if __name__=='__main__': unittest.main()
