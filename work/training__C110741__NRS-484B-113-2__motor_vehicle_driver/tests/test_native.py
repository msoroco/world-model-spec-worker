import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from geometry import check,STOPS
from controller import ReverseController,ReverseKnobs
from engineering import parameters,evaluate_trigger


class ReverseCrosswalkUnit(unittest.TestCase):
    def test_authored_pair(self):
        outcomes=check()['cases']
        self.assertEqual(outcomes['condition_a']['crosswalk_overlap_m2'],0)
        self.assertGreater(outcomes['condition_b']['crosswalk_overlap_m2'],3)
        self.assertEqual(outcomes['condition_b']['intersection_overlap_m2'],0)

    def test_observed_endpoint_requests_reverse_stop(self):
        controller=ReverseController(STOPS['condition_b'],ReverseKnobs())
        command=controller.step(x_m=-14,y_m=-1.75,heading_rad=0,
                                signed_forward_speed_m_s=0)
        self.assertTrue(command['reverse'])
        self.assertTrue(command['hand_brake'])
        self.assertEqual(command['throttle'],0)

    def test_distinct_fallbacks_keep_law_and_recording(self):
        base=parameters('condition_b','primary')['knobs']
        changed=[]
        for candidate in ('fallback1','fallback2','fallback3'):
            knobs=parameters('condition_b',candidate)['knobs']
            changed.append({key for key in base if base[key]!=knobs[key]})
            self.assertEqual((knobs['rate_hz'],knobs['duration_s']),(20,24))
        self.assertEqual(changed,[{'lateral_gain'},{'brake_margin_m'},
                                  {'overview_fov_deg'}])

    def test_fallback_requires_source_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'metrics.json'
            path.write_text(json.dumps({'source_kind':'original_native_and_video',
                                        'max_reverse_cross_track_error_m':.3}))
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertTrue(evaluate_trigger('fallback1',path,digest))
            path.write_text(path.read_text()+' ')
            with self.assertRaisesRegex(ValueError,'hash differs'):
                evaluate_trigger('fallback1',path,digest)


if __name__=='__main__':unittest.main()
