from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from cameras import camera_plan
from engineering import CANDIDATES,CASES,evaluate_trigger,parameters
from geometry import check as geometry_check,route
from measure import measure,synthetic
from runner import check

class NativeDraftTest(unittest.TestCase):
    def test_geometry_and_route(self):
        self.assertTrue(geometry_check()['passed'])
        self.assertGreater(len(route()),700)

    def test_candidate_isolation_and_camera(self):
        for case in CASES:
            base=parameters(case,'primary')['knobs']
            for candidate in CANDIDATES:
                knobs=parameters(case,candidate)['knobs']
                self.assertEqual(sum(knobs[key]!=base[key] for key in base),0 if candidate=='primary' else 1)
                self.assertEqual(len(camera_plan(candidate)),4)

    def test_exact_config_check(self):
        config=json.loads(Path('config.json').read_text())
        self.assertEqual(check(config)['route_samples'],len(route()))
        bad=dict(config,rate_hz=19)
        with self.assertRaisesRegex(ValueError,'Capture profile'):
            check(bad)

    def test_synthetic_positive_and_negative(self):
        with tempfile.TemporaryDirectory() as temp:
            outcomes=[]
            for case in CASES:
                path=Path(temp)/(case+'.json')
                path.write_text(json.dumps(synthetic(case)))
                digest=hashlib.sha256(path.read_bytes()).hexdigest()
                outcomes.append(measure(path,digest)['yielded_to_crosswalk_pedestrian'])
                with self.assertRaisesRegex(ValueError,'Source bytes'):
                    measure(path,'0'*64)
            self.assertEqual(outcomes,[True,False,True,True])

    def test_fallback_requires_bound_original_metrics(self):
        metrics={'source_kind':'original_native_and_video',
                 'max_route_cross_track_error_m':.5,
                 'min_ego_half_pedestrian_clearance_s':.5,
                 'min_crosswalk_or_body_pixel_margin_px':30}
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'metrics.json'
            source.write_text(json.dumps(metrics))
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            for candidate in CANDIDATES[1:]:
                self.assertTrue(evaluate_trigger(candidate,metrics,source,digest))
                with self.assertRaisesRegex(ValueError,'hash'):
                    evaluate_trigger(candidate,metrics,source,'0'*64)

if __name__=='__main__':unittest.main()
