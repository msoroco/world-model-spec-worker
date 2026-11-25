"""CPU checks for reviewed-source gate and original trace writer."""
import json
from pathlib import Path
import tempfile
import unittest

from native_runner import TraceCapture, reviewed_source


class NativeRunnerTests(unittest.TestCase):
    def test_diagnostic_site_cannot_enter_native(self):
        root = Path(__file__).resolve().parents[1]
        case_id = 'testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver__all_prerequisites'
        with self.assertRaisesRegex(ValueError, 'reviewed original site provenance'):
            reviewed_source(root / 'cases' / 'all_prerequisites', case_id)

    def test_original_trace_has_source_frame_and_position(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'trace.jsonl'
            writer = TraceCapture(path)
            writer.capture(71, 3.55, [2.0, 1.5], 'exact-case')
            writer.close()
            self.assertEqual(json.loads(path.read_text()), {
                'frame': 71, 'time_s': 3.55,
                'position_m': [2.0, 1.5, 0.0], 'case_id': 'exact-case'})


if __name__ == '__main__':
    unittest.main()
