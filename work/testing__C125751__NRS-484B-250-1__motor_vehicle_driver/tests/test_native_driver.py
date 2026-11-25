import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_driver import control_step
from test_signal_crossing import packet


def body(x, y):
    return [[x-.2, y-.2], [x+.2, y-.2], [x+.2, y+.2], [x-.2, y+.2]]


class NativeDriverTest(unittest.TestCase):
    def test_other_first_yield_uses_body_and_live_signal(self):
        spec = {'other_first': True, 'ego_response_request': 'yield'}
        p = packet()
        s = control_step(spec, p, {}, frame=0, ego_body=body(-8, 0),
                         other_body=body(0, -8), light_readback='Green')
        self.assertEqual(s['request'], 'brake')
        s = control_step(spec, p, s, frame=1, ego_body=body(-6, 0),
                         other_body=body(0, 0), light_readback='Green')
        self.assertTrue(s['other_entered'])
        self.assertEqual(s['request'], 'brake')
        s = control_step(spec, p, s, frame=2, ego_body=body(-5, 0),
                         other_body=body(0, 6), light_readback='Red')
        self.assertTrue(s['other_cleared'])
        self.assertEqual(s['request'], 'brake')
        s = control_step(spec, p, s, frame=3, ego_body=body(-4, 0),
                         other_body=body(0, 8), light_readback='Green')
        self.assertEqual(s['request'], 'proceed')

    def test_missing_signal_and_false_exit_fail_closed(self):
        spec = {'other_first': True, 'ego_response_request': 'yield'}
        p = packet()
        s = control_step(spec, p, {}, frame=0, ego_body=body(-8, 0),
                         other_body=body(0, -8), light_readback=None)
        self.assertEqual(s['request'], 'brake')
        s = control_step(spec, p, s, frame=1, ego_body=body(-8, 0),
                         other_body=body(0, 0), light_readback='Green')
        s = control_step(spec, p, s, frame=2, ego_body=body(-8, 0),
                         other_body=body(0, -8), light_readback='Green')
        self.assertFalse(s['other_cleared'])
        self.assertEqual(s['request'], 'brake')
        with self.assertRaisesRegex(ValueError, 'gap'):
            control_step(spec, p, s, frame=4, ego_body=body(-8, 0),
                         other_body=body(0, 8), light_readback='Green')


if __name__ == '__main__':
    unittest.main()
