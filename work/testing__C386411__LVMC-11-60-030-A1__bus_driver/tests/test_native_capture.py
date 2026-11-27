"""Native geometry and source-gate checks for both selected stop positions."""
import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('c386411_native',ROOT/'native_capture.py')
native=importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeGeometryTest(unittest.TestCase):
    def test_equal_hold_and_distinct_positions(self):
        self.assertEqual(native.requested_hold({},'inside'),15)
        self.assertEqual(native.requested_hold({},'outside'),15)
        with self.assertRaisesRegex(ValueError,'unknown stop location'):
            native.requested_hold({},'unknown')
        boundary=[[-42,-8],[-18,-8],[-18,0],[-42,0]]
        self.assertTrue(native.inside_polygon([-30,-4],boundary))
        self.assertFalse(native.inside_polygon([-30,-12],boundary))

    def test_original_source_gate(self):
        source=ROOT/'cases/stand_inside/diagnostic-sources/site.json'
        with self.assertRaisesRegex(ValueError,'original independent'):
            native.read_site(source,native.sha(source))

    def test_steer_both_sides(self):
        class P: x=0;y=0
        class R: yaw=0
        class T: location=P();rotation=R()
        self.assertGreater(native.steer_toward(T(),{'x':10,'y':10}),0)
        self.assertLess(native.steer_toward(T(),{'x':10,'y':-10}),0)


if __name__=='__main__':unittest.main()
