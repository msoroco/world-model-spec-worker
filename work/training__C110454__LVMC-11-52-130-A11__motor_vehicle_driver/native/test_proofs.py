import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parent


def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+".py"))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


engineering=load("engineering")
measurement=load("measure_park")


class ParkingProofs(unittest.TestCase):
    def test_distinct_candidates_fixed_capture(self):
        for case in engineering.CASES:
            plans=[engineering.plan(case,c) for c in engineering.CANDIDATES]
            self.assertEqual(len({json.dumps(p["knobs"],sort_keys=True) for p in plans}),4)
            self.assertTrue(all(p["knobs"]["rate_hz"]==20 and p["knobs"]["duration_s"]==24 for p in plans))

    def test_measured_fallback_triggers(self):
        for candidate,key,low,high in (("fallback1","max_park_route_cross_track_error_m",.1,.8),
                                       ("fallback2","parked_endpoint_speed_m_s",.1,.8),
                                       ("fallback3","min_parked_ego_pixel_margin_px",20,80)):
            with self.subTest(candidate=candidate),tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/"metrics.json"
                for value in (low,high):
                    path.write_text(json.dumps({"source_kind":"native_video_metrics",key:value}))
                    digest=hashlib.sha256(path.read_bytes()).hexdigest()
                    self.assertEqual(engineering.evaluate(candidate,path,digest),
                                     (value==low if candidate=="fallback3" else value==high))
                with self.assertRaisesRegex(ValueError,"hash"):
                    engineering.evaluate(candidate,path,"0"*64)

    def test_saved_measurement_tamper(self):
        source=HERE/"../../../.runtime-work/c110454-lvmc-synthetic/witness_2-native.json"
        with self.assertRaisesRegex(ValueError,"hash"):
            measurement.measure(source,"0"*64)

    def test_saved_measurement_missing_join(self):
        source=HERE/"../../../.runtime-work/c110454-lvmc-synthetic/witness_2-missing-frame.json"
        with self.assertRaisesRegex(ValueError,"join"):
            measurement.measure(source,hashlib.sha256(source.read_bytes()).hexdigest())


if __name__=="__main__":unittest.main()
