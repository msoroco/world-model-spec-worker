import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import execute
from native_capture import capture
from test_native_site import SITE


class RunnerTests(unittest.TestCase):
    def test_missing_reviewed_site_rejects_before_adapter_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "site.json"
            source.write_text(json.dumps({**SITE, "diagnostic_fixture": True}))
            output = root / "output"
            output.mkdir()
            case = "testing__C378304__NRS-484B-413-2__motor_vehicle_driver__continuous100"
            with self.assertRaisesRegex(ValueError, "diagnostic fixture cannot"):
                execute(case, source, hashlib.sha256(source.read_bytes()).hexdigest(),
                        output, "nonexistent_carla_adapter_module", "127.0.0.1", 2000)
            self.assertFalse(list(output.iterdir()))
            source.write_text(json.dumps({**SITE, "frontage_source": ""}))
            with self.assertRaisesRegex(ValueError, "frontage_source"):
                execute(case, source, hashlib.sha256(source.read_bytes()).hexdigest(),
                        output, "nonexistent_carla_adapter_module", "127.0.0.1", 2000)
            self.assertFalse(list(output.iterdir()))

    def test_production_capture_length_is_fixed(self):
        class SourceOnly:
            diagnostic_test_only = False
        case = {"case_id": "a__rain", "target": {"weather_request": "rain",
                "signal_continuity_request": "continuous"}}
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "requires 900 frames"):
                capture(SourceOnly(), SITE, "f" * 64, case, Path(temporary), frames=3)


if __name__ == "__main__":
    unittest.main()
