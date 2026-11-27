import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('c393262_native',ROOT/'native_capture.py')
native=importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeGeometryTest(unittest.TestCase):
    def test_duration_requests_follow_reviewed_designation(self):
        site={'designation':{'applicable_duration_s':15}}
        self.assertEqual([native.requested_hold(site,x) for x in ('below','at','above')],[13,15,17])
        with self.assertRaisesRegex(ValueError,'unknown duration'):
            native.requested_hold(site,'unknown')

    def test_stop_footprint_and_steering(self):
        boundary=[[-2,-2],[2,-2],[2,2],[-2,2]]
        self.assertTrue(native.inside_polygon([0,0],boundary))
        self.assertFalse(native.inside_polygon([3,0],boundary))
        class Point:
            x=0;y=0
        class Rotation:
            yaw=0
        class Transform:
            location=Point();rotation=Rotation()
        self.assertEqual(native.steer_toward(Transform(),{'x':10,'y':0}),0)
        self.assertGreater(native.steer_toward(Transform(),{'x':10,'y':10}),0)
        self.assertLess(native.steer_toward(Transform(),{'x':10,'y':-10}),0)

    def test_synthetic_site_rejected_for_original(self):
        source=ROOT/'cases/park_at/diagnostic-sources/site.json'
        with self.assertRaisesRegex(ValueError,'original independent'):
            native.read_site(source,native.sha(source))
