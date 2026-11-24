import pathlib
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from capture_lifecycle import EVENTS, run


class LifecycleTest(unittest.TestCase):
    def test_saved_processing_after_observed_release(self):
        calls = []
        owner = SimpleNamespace(encoders_closed=True, restoration_verified=True,
                                native_exited=True, owner_released=True)
        def capture():
            calls.append('capture')
            return 'sealed-attempt'
        def process(attempt):
            self.assertEqual(attempt, 'sealed-attempt')
            calls.append('process')
            return 'saved-result'
        receipt = run(capture, process, owner)
        self.assertEqual(receipt['events'], EVENTS)
        self.assertEqual(calls, ['capture', 'process'])

    def test_each_incomplete_native_state_blocks_saved_processing(self):
        for field in ('encoders_closed', 'restoration_verified',
                      'native_exited', 'owner_released'):
            with self.subTest(field=field):
                states = {key: True for key in ('encoders_closed',
                          'restoration_verified', 'native_exited', 'owner_released')}
                states[field] = False
                calls = []
                with self.assertRaisesRegex(RuntimeError, 'Native lifecycle incomplete'):
                    run(lambda: 'sealed-attempt',
                        lambda attempt: calls.append(attempt), SimpleNamespace(**states))
                self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
