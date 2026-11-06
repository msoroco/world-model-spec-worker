import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from engineering import CASES, CANDIDATES, evaluate, plan
from geometry import check


class ParkingBundleProofs(unittest.TestCase):
    def test_fixed_identity_and_distinct_candidates(self):
        self.assertTrue(check()['passed'])
        for case in CASES:
            plans=[plan(case,c) for c in CANDIDATES]
            self.assertEqual(len({json.dumps(p['knobs'],sort_keys=True) for p in plans}),4)
            self.assertTrue(all(p['knobs']['rate_hz']==20 and p['knobs']['duration_s']==24 for p in plans))

    def test_trigger_positive_negative_and_hash(self):
        for candidate,metric,low,high in (
            ('fallback1','max_park_route_cross_track_error_m',.1,.8),
            ('fallback2','parked_endpoint_speed_m_s',.1,.8),
            ('fallback3','min_parked_ego_pixel_margin_px',20,80)):
            with self.subTest(candidate=candidate),tempfile.TemporaryDirectory() as temp:
                source=Path(temp)/'metrics.json'
                for value in (low,high):
                    source.write_text(json.dumps({'source_kind':'native_video_metrics',metric:value}))
                    digest=hashlib.sha256(source.read_bytes()).hexdigest()
                    self.assertEqual(evaluate(candidate,source,digest),
                        value==low if candidate=='fallback3' else value==high)
                with self.assertRaisesRegex(ValueError,'hash'):
                    evaluate(candidate,source,'0'*64)


if __name__=='__main__':
    unittest.main()
