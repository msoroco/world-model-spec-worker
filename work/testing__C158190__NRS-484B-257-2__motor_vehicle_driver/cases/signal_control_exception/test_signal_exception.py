import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import runner
import signal_exception


class SignalExceptionTests(unittest.TestCase):
    def test_exact_authored_control_chain(self):
        receipt = signal_exception.self_check()
        self.assertEqual(receipt['stop_signal_id'], '1581902')
        self.assertEqual(receipt['head_signal_id'], '1581903')
        self.assertFalse(receipt['native_governance_confirmed'])

    def test_exact_case_config(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(runner.validate_config(config)['selected_case_id'], runner.CASE_ID)
        with self.assertRaisesRegex(ValueError, 'green engineering target'):
            runner.validate_config(dict(config, target_signal_state='Red'))

    def test_phase_and_actor_clearance_control(self):
        light = SimpleNamespace(get_state=lambda: 'Green')
        stage = runner.SignalStage(light)
        self.assertEqual(stage.target(2, 2, before_reference=True,
                                      within_intersection=False, other_clear=False), 0)
        self.assertEqual(stage.target(2, 2, before_reference=True,
                                      within_intersection=False, other_clear=True), 5)
        red = runner.SignalStage(SimpleNamespace(get_state=lambda: 'Red'))
        with self.assertRaisesRegex(ValueError, 'left requested green phase'):
            red.target(2, 2, before_reference=True,
                       within_intersection=False, other_clear=True)


if __name__ == '__main__':
    unittest.main()
